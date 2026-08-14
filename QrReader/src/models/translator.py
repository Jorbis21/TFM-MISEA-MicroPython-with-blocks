from utils.strings import t
from utils.constants import TTSMode


class MicrobitCompiler:
    def __init__(self, config_dir, json_manager):
        self.config_dir = config_dir
        self.json_manager = json_manager
        self.symbols_table = self.json_manager.build_symbols_table()
        
        self.var_cont = 0        
        self.tts_mode = TTSMode.PC.value

        self.analysis_mode = False
        self.var_needs = []
        self.presaved_answers = []

    def set_mode_tts(self, mode):
        self.tts_mode = mode

    def _is_num_value(self, token):
        try:
            float(token)
            return True
        except ValueError:
            return False
        
    def normalize_text(self, text, is_variable=False):
        if not text: return ""
        text = text.strip().lower()
        replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u'}
        for original, new in replacements.items():
            text = text.replace(original, new)
        if is_variable:
            text = text.replace(" ", "_")
        return text

    def _apply_type(self, text):
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

        # Notas musicales, en solfeo (do, re, mi...) o en notacion anglosajona
        # (c, d, e...) - se admiten las dos indistintamente, incluso mezcladas
        # en la misma secuencia, y se traducen siempre a la notacion que
        # espera music.play(). Se exigen al menos 2 palabras reconocidas como
        # notas para no confundir una palabra suelta (p.ej. "a") con una
        # melodia de una sola nota.
        # Musical notes, in solfege (do, re, mi...) or letter notation
        # (c, d, e...) - both are accepted indistinctly, even mixed within
        # the same sequence, and always get translated to the notation
        # music.play() expects. At least 2 recognized note words are
        # required, so a lone word (e.g. "a") isn't mistaken for a
        # one-note melody.
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

        # Sustituye cada palabra numérica por su dígito antes del parseo decimal,
        # para que "tres coma cinco" / "three point five" den 3.5 en vez de
        # quedarse como texto (esto no funcionaba ni en el original: solo
        # sustituía si el texto ENTERO era una única palabra numérica).
        # Substitutes each number word for its digit before decimal parsing,
        # so "tres coma cinco" / "three point five" produce 3.5 instead of
        # staying as text (this didn't work even in the original: it only
        # substituted when the WHOLE text was a single number word).
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

    # --- LÓGICA DE VARIABLES (MVC PURO - 2 PASADAS) ---

    def analize_matrix(self, command_matrix):
        """Pasada 1: Recorre la matriz lógicamente para listar qué interacciones necesita."""
        self.analysis_mode = True
        self.var_needs = []
        self._run_internal_generation(command_matrix, None) # Compila en el vacío
        self.analysis_mode = False
        return self.var_needs

    def _solve_variable(self, block_type, context=""):
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
        name = self._solve_variable("declare_var", t("context_declare_var"))

        # Si hay un bloque a la derecha de "declarar variable" (una
        # referencia a otra variable, un "value variable", un numero...) se
        # usa ESE como valor inicial. Antes se preguntaba siempre un valor
        # nuevo por voz y se descartaba (tokens.clear()) cualquier bloque que
        # hubiera ahi, ignorandolo por completo.
        # If there's a block to the right of "declarar variable" (a
        # reference to another variable, a "value variable", a number...)
        # THAT is used as the initial value. It used to always ask for a new
        # value by voice and discard (tokens.clear()) whatever block was
        # actually there, ignoring it completely.
        if tokens:
            value_code = self._consume_vc_arg(tokens, context=t("context_value_for", name=name))
            if "# ERROR" in value_code:
                return value_code
        else:
            text_value = self._solve_variable("assign_val", t("context_value_for", name=name))
            value_code, _ = self._apply_type(text_value)

        return f"{name} = {value_code}"

    def _manage_asignation(self, tokens, context=""):
        text_value = self._solve_variable("assign_val", context)
        value_code, _ = self._apply_type(text_value)
        return value_code

    def _manage_reference(self, tokens, context=""):
        return self._solve_variable("reference_var", context)

    # --- MOTOR PRINCIPAL ---

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
        if not tokens: return ""
        
        def check_row(block, expect, remain_tokens):
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
        if not tokens: return ""
        def check_stack(block, expect):
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