class MicrobitCompiler:

    def __init__(self, config_dir, json_manager):
        self.config_dir = config_dir
        self.json_manager = json_manager
        self.symbols_table = self.json_manager.build_symbols_table()
        
        self.var_memory = []  
        self.var_cont = 0        
        self.tts_mode = "pc"  

        self.analysis_mode = False
        self.var_needs = []
        self.presaved_answers = []

    def set_mode_tts(self, mode):
        """Cambia el modo de tts"""
        """Change the tts mode"""
        self.tts_mode = mode

    def _is_num_value(self, token):
        """Comprueba si un valor es numero"""
        """Checks if a value is num"""
        try:
            float(token)
            return True
        except ValueError:
            return False
        
    def normalize_text(self, text, is_variable=False):
        """Limpia el texto de tildes"""
        """Cleans the text of accents"""
        if not text: return ""
        text = text.strip().lower()
        replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u'}
        for original, new in replacements.items():
            text = text.replace(original, new)
        if is_variable:
            text = text.replace(" ", "_")
        return text

    def _apply_type(self, text):
        """Limpia el texto de numeros en letras"""
        """Cleans the text of numbers in text"""
        text = text.strip().lower()
        letters_nums = {
            "cero": "0", "uno": "1", "dos": "2", "tres": "3", "cuatro": "4",
            "cinco": "5", "seis": "6", "siete": "7", "ocho": "8", "nueve": "9",
            "diez": "10", "once": "11", "doce": "12", "trece": "13", "catorce": "14",
            "quince": "15", "dieciséis": "16", "diecisiete": "17", "dieciocho": "18",
            "diecinueve": "19", "veinte": "20", "treinta": "30", "cuarenta": "40",
            "cincuenta": "50", "sesenta": "60", "setenta": "70", "ochenta": "80",
            "noventa": "90", "cien": "100"
        }
        
        if text.startswith("número ") or text.startswith("numero "):
            text = text.replace("número ", "", 1).replace("numero ", "", 1).strip()

        multi_text = text.replace(" coma ", " ").replace(",", " ").replace(" y ", " ")
        multi_words = [p for p in multi_text.split() if p]
        multi_words = [str(letters_nums.get(p, p)) for p in multi_words]
        
        is_image = False
        img_words = multi_words.copy()
        
        if img_words and img_words[0] == "imagen":
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
            
        if text in letters_nums:
            text = letters_nums[text]
            
        parsed_text = text.replace(" coma ", ".").replace(" con ", ".").replace(",", ".").replace(" .", ".").replace(". ", ".")
        
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
        """Recorre la matriz para listar qué interacciones necesita"""
        """Iterate through the matrix to list which interactions are needed"""
        self.analysis_mode = True
        self.var_needs = []
        self._run_internal_generation(command_matrix, None)
        self.analysis_mode = False
        return self.var_needs

    def _solve_variable(self, block_type, context=""):
        """Resuelve la variable"""
        """Resolves the variable"""
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
        """Maneja la declaracion"""
        """Manages the declaration"""
        name = self._solve_variable("declare_var", "declarar una variable nueva")
        text_value = self._solve_variable("assign_val", f"el valor para {name}")
        
        value_code, real_value = self._apply_type(text_value)
        self.var_memory.append({name: real_value})
        tokens.clear() 
        return f"{name} = {value_code}"

    def _manage_asignation(self, tokens, context=""):
        """Maneja la asignacion"""
        """Manages the asignation"""
        text_value = self._solve_variable("assign_val", context)
        value_code, _ = self._apply_type(text_value)
        return value_code

    def _manage_reference(self, tokens, context=""):
        """Maneja la referencia"""
        """Manages the reference"""
        return self._solve_variable("reference_var", context)

    def generate_code(self, command_matrix, out_path, answers=None):
        """Genera el archivo usando las respuestas"""
        """Generates the file using the answers"""
        if answers is not None:
            self.presaved_answers = answers.copy()
            
        final_code = self._run_internal_generation(command_matrix, out_path)
        
        if out_path and not self.analysis_mode:
            with open(out_path, "w", encoding="utf-8") as file:
                file.write("\n".join(final_code) + "\n")
            print("Código compilado con éxito.")

    def _run_internal_generation(self, command_matrix, out_path):
        """Corre la generacion de codigo interna"""
        """Runs the internal code generation"""
        self.var_memory = []
        self.var_cont = 0
            
        if not command_matrix: return []

        final_code = [
            "from microbit import *",
            "import speech",
            "import music",
            "import random",
            "from math import *",
            "\n# --- Sonido de inicialización ---",
            "music.pitch(587, 100)",
            "music.pitch(698, 100)",
            "music.pitch(783, 100)",
            "# --- Programa Principal ---\n"
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
        """Procesa la fila de tokens"""
        """Process the tokens row"""
        if not tokens: return ""
        error_stack = []
        
        def check_row(block, expect, remain_tokens):
            error_stack.append({"block": block, "expect": expect})
            if not remain_tokens:
                error = error_stack.pop()
                return f"# ERROR: El bloque '{error['block']}' esperaba {error['expect']} a su derecha."
            error_stack.pop()
            return None

        first_block = tokens.pop(0)
        if self._is_num_value(first_block):
            info = {"code": str(first_block), "type": "value"}
        else:
            info = self.symbols_table.get(first_block, {})
        
        if not info:
            return f"# ERROR: El bloque '{first_block}' es desconocido o no está en el diccionario."
            
        type = info.get("type", "")
        base_code = info.get("code", str(first_block))
        
        if type == "declare_var": return self._manage_declaration(tokens)
        elif type == "assign_val": return self._manage_asignation(tokens, context="una orden general")
        elif type == "reference_var": return self._manage_reference(tokens, context="una orden general")

        if type == "control_method":
            stack_error = check_row(first_block, "un sujeto o sensor", tokens)
            if stack_error: return stack_error
            subject = self._consume_vc_arg(tokens, context=f"el método de control de {first_block}")
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
            stack_error = check_row(first_block, "un argumento o condición", tokens)
            if stack_error: return stack_error
            arg = self._consume_vc_arg(tokens, context=f"la función {first_block}")
            if "# ERROR" in arg: return arg
            return f"if {base_code}({arg}):"

        elif type == "method":
            stack_error = check_row(first_block, "un sujeto para aplicarse", tokens)
            if stack_error: return stack_error
            subject = self._consume_vc_arg(tokens, context=f"el sujeto de {first_block}")
            if "# ERROR" in subject: return subject
            
            num_args = info.get("args", 0)
            extra_args = []
            satisfied_args = 0
            while satisfied_args < num_args:
                error_arg = check_row(first_block, f"el argumento número {satisfied_args+1}", tokens)
                if error_arg: return error_arg
                arg_ext = self._consume_vc_arg(tokens, context=f"el argumento de {first_block}")
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
                if self.tts_mode == "pc": return f"print('TTS:' + str({arg_var}))\n{indent}{res}"
                elif self.tts_mode == "board": return f"speech.say(str({arg_var}))\n{indent}{res}"
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
                    error_arg = check_row(first_block, f"el argumento número {satisfied_args+1}", tokens)
                    if error_arg: return error_arg
                    arg_func = self._consume_vc_arg(tokens, context=f"el argumento de {first_block}")
                    if "# ERROR" in arg_func: return arg_func
                    args.append(arg_func)
                    satisfied_args += len(arg_func.split(","))
                res = f"{base_code}({', '.join(args)})"

            if "display.scroll" in base_code or "display.show" in base_code:
                arg_var = args[0] if args else '""'
                if "Image" in arg_var or ":" in arg_var: return res
                if self.tts_mode == "pc": return f"print('TTS:' + str({arg_var}))\n{indent}{res}"
                elif self.tts_mode == "board": return f"speech.say(str({arg_var}))\n{indent}{res}"
            return res
            
        elif type == "control":
            cond = ""
            if tokens:
                cond = self._consume_vc_arg(tokens, context=f"la condición de {first_block}")
                if "# ERROR" in cond: return cond
            
            clean_code = base_code.replace(":", "").strip()
            if cond: return f"{clean_code} {cond}:"
            else: return f"{clean_code}:"
                
        else:
            tokens.insert(0, first_block)
            res = self._consume_vc_arg(tokens, context=f"el bloque junto a {first_block}")
            if not res: return f"# ERROR: El bloque '{first_block}' está suelto."
            return res

    def _consume_vc_arg(self, tokens, context=""):
        """Consume el argumento the tipo vc"""
        """Consume the var and cond arguments"""
        if not tokens: return ""
        error_stack = []
        def check_stack(block, expect):
            error_stack.append({"block": block, "expect": expect})
            if not tokens:
                error = error_stack.pop()
                return f"\n# ERROR: Después de '{error['block']}', faltaba {error['expect']}."
            error_stack.pop()
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
                error = check_stack(op, "otra condición")
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
                    error = check_stack(method, f"argumento {satisfied_args+1}")
                    if error: return result + error
                    arg_func = self._consume_vc_arg(tokens, context=f"argumento de {method}")
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