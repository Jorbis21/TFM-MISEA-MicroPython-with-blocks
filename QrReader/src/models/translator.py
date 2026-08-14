from utils.strings import t
from utils.constants import TTSMode


class MicrobitCompiler:
    """Traduce la matriz de bloques detectados por la cámara a código MicroPython, en dos pasadas: una de análisis (para saber qué preguntar por voz) y otra de generación (con las respuestas ya dadas)"""
    """Translates the block matrix detected by the camera into MicroPython code, in two passes: an analysis one (to know what to ask by voice) and a generation one (with the answers already given)"""

    def __init__(self, config_dir, json_manager):
        """Construye la tabla de símbolos a partir del diccionario, y deja el compilador listo en modo generación (no análisis), sin variables ni respuestas precargadas"""
        """Builds the symbols table from the dictionary, and leaves the compiler ready in generation mode (not analysis), with no variables or preloaded answers"""
        self.config_dir = config_dir
        self.json_manager = json_manager
        self.symbols_table = self.json_manager.build_symbols_table()
        
        self.var_cont = 0        
        self.tts_mode = TTSMode.PC.value

        self.analysis_mode = False
        self.var_needs = []
        self.presaved_answers = []

    def set_mode_tts(self, mode):
        """Cambia el modo de lectura en voz alta de los valores mostrados, para las próximas generaciones de código"""
        """Changes the voice-reading mode for the displayed values, for the next code generations"""
        self.tts_mode = mode

    def _is_num_value(self, token):
        """Indica si el texto se puede interpretar como un número (entero o decimal)"""
        """Indicates whether the text can be interpreted as a number (integer or decimal)"""
        try:
            float(token)
            return True
        except ValueError:
            return False
        
    def normalize_text(self, text, is_variable=False):
        """Limpia un texto para usarlo en el código generado: quita espacios sobrantes, pasa a minúsculas, quita acentos, y si es para un nombre de variable, sustituye los espacios por guiones bajos"""
        """Cleans up a text to use it in the generated code: strips extra spaces, lowercases it, removes accents, and if it's for a variable name, replaces spaces with underscores"""
        if not text: return ""
        text = text.strip().lower()
        replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u'}
        for original, new in replacements.items():
            text = text.replace(original, new)
        if is_variable:
            text = text.replace(" ", "_")
        return text

    def _apply_type(self, text):
        """Convierte un texto dicho o escrito por el usuario en el literal de Python que le corresponde: notas musicales, una imagen en formato Image(), una terna RGB, un número (entero o decimal, admitiendo palabras numéricas), o si nada de eso encaja, una cadena de texto. Devuelve una tupla (código, valor)"""
        """Converts a text spoken or typed by the user into its corresponding Python literal: musical notes, an image in Image() format, an RGB triplet, a number (integer or decimal, accepting number words), or if none of that fits, a text string. Returns a tuple (code, value)"""
        text = text.strip().lower()
        letters_nums = t("number_words")

        for prefix in t("number_prefix"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        multi_text = text
        for connector in t("decimal_connectors"):
            multi_text = multi_text.replace(connector, " ")
        multi_text = multi_text.replace(",", " ").replace(t("junction_word"), " ")
        multi_words = [p for p in multi_text.split() if p]
        multi_words = [str(letters_nums.get(p, p)) for p in multi_words]

        note_map = t("note_names")
        if len(multi_words) >= 2 and all(w in note_map for w in multi_words):
            notes = [note_map[w] for w in multi_words]
            quoted = ", ".join(f"'{n}'" for n in notes)
            return f"[{quoted}]", notes

        is_image = False
        img_words = multi_words.copy()
        
        if img_words and img_words[0] == t("image_word"):
            is_image = True
            img_words.pop(0) 
            
        if img_words and all(p.isdigit() and len(p) == 1 for p in img_words):
            if is_image or len(img_words) > 3:
                digits = "".join(img_words)
                digits = digits.ljust(25, '0')[:25] 
                img_form = f"{digits[0:5]}:{digits[5:10]}:{digits[10:15]}:{digits[15:20]}:{digits[20:25]}"
                return f"Image('{img_form}')", img_form

        if len(multi_words) == 3:
            try:
                values = [int(p) for p in multi_words]
                return f"{values[0]}, {values[1]}, {values[2]}", values
            except ValueError:
                pass

        substituted_text = " ".join(str(letters_nums.get(p, p)) for p in text.split())

        parsed_text = substituted_text
        for connector in t("decimal_connectors"):
            parsed_text = parsed_text.replace(connector, ".")
        parsed_text = parsed_text.replace(",", ".").replace(" .", ".").replace(". ", ".")
        
        try:
            val = int(parsed_text)
            return str(val), val
        except ValueError:
            pass
        try:
            val = float(parsed_text)
            return str(val), val
        except ValueError:
            pass
            
        clean_text = self.normalize_text(text, is_variable=False)
        return f'"{clean_text}"', clean_text


    def analize_matrix(self, command_matrix):
        """Pasada 1: Recorre la matriz lógicamente para listar qué interacciones necesita."""
        self.analysis_mode = True
        self.var_needs = []
        self._run_internal_generation(command_matrix, None)
        self.analysis_mode = False
        return self.var_needs

    def _solve_variable(self, block_type, context=""):
        """En modo análisis, apunta que hace falta preguntar esto por voz y devuelve un nombre provisional; en modo generación, consume la siguiente respuesta ya dada (o genera un nombre provisional si no quedan respuestas)"""
        """In analysis mode, notes that this needs to be asked by voice and returns a provisional name; in generation mode, consumes the next already-given answer (or generates a provisional name if no answers remain)"""
        if self.analysis_mode:
            self.var_needs.append({"type": block_type, "context": context})
            self.var_cont += 1
            return f"var_{self.var_cont}" 
        else:
            if self.presaved_answers:
                return self.presaved_answers.pop(0)
            self.var_cont += 1
            return f"var_{self.var_cont}"

    def _manage_declaration(self, tokens):
        """Genera la línea de declaración de una variable nueva: pide su nombre, y si hay otro bloque a la derecha lo usa como valor inicial; si no hay ninguno, pregunta el valor por voz"""
        """Generates a new variable's declaration line: asks for its name, and if there's another block to the right it's used as the initial value; if there isn't one, asks for the value by voice"""
        name = self._solve_variable("declare_var", t("context_declare_var"))

        if tokens:
            value_code = self._consume_vc_arg(tokens, context=t("context_value_for", name=name))
            if "# ERROR" in value_code:
                return value_code
        else:
            text_value = self._solve_variable("assign_val", t("context_value_for", name=name))
            value_code, _ = self._apply_type(text_value)

        return f"{name} = {value_code}"

    def _manage_asignation(self, tokens, context=""):
        """Pregunta un valor por voz (bloque 'valor variable') y lo convierte en su literal de Python correspondiente"""
        """Asks for a value by voice ('value variable' block) and converts it into its corresponding Python literal"""
        text_value = self._solve_variable("assign_val", context)
        value_code, _ = self._apply_type(text_value)
        return value_code

    def _manage_reference(self, tokens, context=""):
        """Pregunta por voz a qué variable existente se refiere el bloque 'variable', y devuelve su nombre"""
        """Asks by voice which existing variable the 'variable' block refers to, and returns its name"""
        return self._solve_variable("reference_var", context)


    def generate_code(self, command_matrix, out_path, answers=None):
        """Pasada 2: Genera el archivo usando las answers precalculadas."""
        if answers is not None:
            self.presaved_answers = answers.copy()
            
        final_code = self._run_internal_generation(command_matrix, out_path)
        
        if out_path and not self.analysis_mode:
            with open(out_path, "w", encoding="utf-8") as file:
                file.write("\n".join(final_code) + "\n")
            print("Código compilado con éxito.")

    def _run_internal_generation(self, command_matrix, out_path):
        """Recorre la matriz fila por fila, calculando la indentación según el desplazamiento físico de cada una, y traduce cada fila a una línea de código; antepone la cabecera fija (imports y sonido de inicio)"""
        """Walks the matrix row by row, computing the indentation from each row's physical offset, and translates each row into a line of code; prepends the fixed header (imports and startup sound)"""
        self.var_cont = 0
            
        if not command_matrix: return []

        final_code = [
            "from microbit import *",
            "import speech",
            "import music",
            "import random",
            "from math import *",
            f"\n{t('marker_init_sound')}",
            "music.pitch(587, 100)",
            "music.pitch(698, 100)",
            "music.pitch(783, 100)",
            f"{t('marker_main_program')}\n"
        ]

        active_levels = [0] 
        for row in command_matrix:
            fisical_tabs_num = 0
            for elem in row:
                if elem == "": fisical_tabs_num += 1
                else: break
            
            tokens = [e for e in row if e != ""]
            if not tokens: continue

            while len(active_levels) > 1 and fisical_tabs_num < active_levels[-1]:
                active_levels.pop()
                
            if fisical_tabs_num > active_levels[-1]:
                active_levels.append(fisical_tabs_num)
                
            logic_level = len(active_levels) - 1
            indentation = "    " * logic_level  
            
            translated_row = self._process_token_rows(tokens, indentation)
            final_code.append(indentation + translated_row)

        return final_code

    def _process_token_rows(self, tokens, indent=""):
        """Traduce una fila de bloques (ya sin las celdas vacías de indentación) a su línea de código MicroPython equivalente, según el tipo del primer bloque (control, función, operador lógico, variable...)"""
        """Translates a row of blocks (already without the empty indentation cells) into its equivalent MicroPython code line, according to the type of the first block (control, function, logic operator, variable...)"""
        if not tokens: return ""
        
        def check_row(block, expect, remain_tokens):
            """Comprueba que todavía queden bloques por consumir; si no, arma el mensaje de error de 'falta algo a la derecha de X'"""
            """Checks that there are still blocks left to consume; if not, builds the 'missing something to the right of X' error message"""
            if not remain_tokens:
                return t("err_expected_right", block=block, expect=expect)
            return None

        first_block = tokens.pop(0)
        if self._is_num_value(first_block):
            info = {"code": str(first_block), "type": "value"}
        else:
            info = self.symbols_table.get(first_block, {})
        
        if not info:
            return t("err_unknown_block", block=first_block)
            
        type = info.get("type", "")
        base_code = info.get("code", str(first_block))
        
        if type == "declare_var": return self._manage_declaration(tokens)
        elif type == "assign_val": return self._manage_asignation(tokens, context=t("context_general_order"))
        elif type == "reference_var": return self._manage_reference(tokens, context=t("context_general_order"))

        if type == "control_method":
            stack_error = check_row(first_block, t("context_control_method_subject"), tokens)
            if stack_error: return stack_error
            subject = self._consume_vc_arg(tokens, context=t("context_control_method_of", block=first_block))
            if "# ERROR" in subject: return subject
            
            if ".is_pressed" in base_code or ".is_touched" in base_code:
                if " and " in subject or " or " in subject:
                    parts = subject.replace(" and ", " _AND_ ").replace(" or ", " _OR_ ").split()
                    final_subject = []
                    for part in parts:
                        if part == "_AND_": final_subject.append("and")
                        elif part == "_OR_": final_subject.append("or")
                        else:
                            if "pin" in part or "logo" in part: final_subject.append(f"{part}.is_touched()")
                            else: final_subject.append(f"{part}.is_pressed()")
                    return f"if {' '.join(final_subject)}:"
                else:
                    if "pin" in subject or "logo" in subject: return f"if {subject}.is_touched():"
                    else: return f"if {subject}.is_pressed():"
            if base_code.endswith(")"): return f"if {subject}{base_code}:"
            else: return f"if {subject}{base_code}():"

        elif type == "control_function":
            stack_error = check_row(first_block, t("context_control_function_arg"), tokens)
            if stack_error: return stack_error
            arg = self._consume_vc_arg(tokens, context=t("context_function_of", block=first_block))
            if "# ERROR" in arg: return arg
            return f"if {base_code}({arg}):"

        elif type == "method":
            stack_error = check_row(first_block, t("context_method_subject_needed"), tokens)
            if stack_error: return stack_error
            subject = self._consume_vc_arg(tokens, context=t("context_subject_of", block=first_block))
            if "# ERROR" in subject: return subject
            
            num_args = info.get("args", 0)
            extra_args = []
            satisfied_args = 0
            while satisfied_args < num_args:
                error_arg = check_row(first_block, t("context_arg_number", n=satisfied_args+1), tokens)
                if error_arg: return error_arg
                arg_ext = self._consume_vc_arg(tokens, context=t("context_arg_of", block=first_block))
                if "# ERROR" in arg_ext: return arg_ext
                extra_args.append(arg_ext)
                satisfied_args += len(arg_ext.split(","))
            
            if extra_args: res = f"{subject}{base_code}({', '.join(extra_args)})"
            else:
                if base_code.endswith(")"): res = f"{subject}{base_code}"
                else: res = f"{subject}{base_code}()"
                
            if subject == "display" and ("scroll" in base_code or "show" in base_code):
                arg_var = extra_args[0] if extra_args else '""'
                if "Image" in arg_var or ":" in arg_var: return res
                if self.tts_mode == TTSMode.PC.value: return f"print('TTS:' + str({arg_var}))\n{indent}{res}"
                elif self.tts_mode == TTSMode.BOARD.value: return f"speech.say(str({arg_var}))\n{indent}{res}"
            return res
                
        elif type == "function":
            num_args = info.get("args", 1)
            args = []
            if num_args == 0:
                if base_code.endswith(")"): res = base_code
                else: res = f"{base_code}()"
            else:
                satisfied_args = 0
                while satisfied_args < num_args:
                    error_arg = check_row(first_block, t("context_arg_number", n=satisfied_args+1), tokens)
                    if error_arg: return error_arg
                    arg_func = self._consume_vc_arg(tokens, context=t("context_arg_of", block=first_block))
                    if "# ERROR" in arg_func: return arg_func
                    args.append(arg_func)
                    satisfied_args += len(arg_func.split(","))
                res = f"{base_code}({', '.join(args)})"

            if "display.scroll" in base_code or "display.show" in base_code:
                arg_var = args[0] if args else '""'
                if "Image" in arg_var or ":" in arg_var: return res
                if self.tts_mode == TTSMode.PC.value: return f"print('TTS:' + str({arg_var}))\n{indent}{res}"
                elif self.tts_mode == TTSMode.BOARD.value: return f"speech.say(str({arg_var}))\n{indent}{res}"
            return res
            
        elif type == "control":
            cond = ""
            if tokens:
                cond = self._consume_vc_arg(tokens, context=t("context_condition_of", block=first_block))
                if "# ERROR" in cond: return cond
            
            clean_code = base_code.replace(":", "").strip()
            if cond: return f"{clean_code} {cond}:"
            else: return f"{clean_code}:"
                
        else:
            tokens.insert(0, first_block)
            res = self._consume_vc_arg(tokens, context=t("context_block_next_to", block=first_block))
            if not res: return t("err_loose_block", block=first_block)
            return res

    def _consume_vc_arg(self, tokens, context=""):
        """Consume y resuelve el siguiente bloque como argumento de una función o método: un número literal, una referencia a variable, un valor pedido por voz, o el código base de cualquier otro bloque"""
        """Consumes and resolves the next block as a function or method argument: a literal number, a variable reference, a value asked by voice, or any other block's base code"""
        if not tokens: return ""
        def check_stack(block, expect):
            """Comprueba que todavía queden bloques por consumir; si no, arma el mensaje de error de 'falta algo detrás de X'"""
            """Checks that there are still blocks left to consume; if not, builds the 'missing something after X' error message"""
            if not tokens:
                return t("err_missing_after", block=block, expect=expect)
            return None

        val = tokens.pop(0)
        if self._is_num_value(val): result = str(val)
        else:
            info = self.symbols_table.get(val, {})
            type_val = info.get("type", "")
            
            if type_val == "reference_var": result = self._manage_reference(tokens, context)
            elif type_val == "assign_val": result = self._manage_asignation(tokens, context)
            else: result = info.get("code", val)
            
        while tokens:
            if self._is_num_value(tokens[0]): break
            next_info = self.symbols_table.get(tokens[0], {})
            next_type = next_info.get("type")
            
            if next_type == "logic_operator":
                op = tokens.pop(0)
                result += next_info.get("code", op)
                error = check_stack(op, t("context_another_condition"))
                if error: return result + error
                if tokens: result += self._consume_vc_arg(tokens, context)
                break
                
            elif next_type == "method":
                method = tokens.pop(0)
                method_code = next_info.get("code", method)
                
                if ".is_pressed" in method_code or ".is_touched" in method_code:
                    if "pin" in result or "logo" in result: method_code = ".is_touched()"
                    else: method_code = ".is_pressed()"

                num_args = next_info.get("args", 0)
                extra_args = []
                satisfied_args = 0
                while satisfied_args < num_args:
                    error = check_stack(method, t("context_arg_n_short", n=satisfied_args+1))
                    if error: return result + error
                    arg_func = self._consume_vc_arg(tokens, context=t("context_arg_of_short", block=method))
                    if "# ERROR" in arg_func: return result + arg_func
                    extra_args.append(arg_func) 
                    satisfied_args += len(arg_func.split(","))
                        
                if extra_args: result += f"{method_code}({', '.join(extra_args)})"
                else:
                    if method_code.endswith(")"): result += method_code
                    else: result += f"{method_code}()"
            else:
                break
        return result