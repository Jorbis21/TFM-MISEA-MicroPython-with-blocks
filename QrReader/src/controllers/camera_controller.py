import threading, re, os
from utils.constants import TTSMode, EventType
from controllers.camera_worker import CameraWorker

class CameraController:
    
    def __init__(self, workspace_dir, code_dir, traducer, file_manager, audio_service, vision, ai_manager, voice_manager):
        self.workspace_dir = workspace_dir
        self.code_dir = code_dir
        self.traducer = traducer
        self.file_manager = file_manager
        self.audio_service = audio_service
        self.vision = vision
        self.ai_manager = ai_manager
        self.voice_manager = voice_manager

        self.camera_thr = CameraWorker(self.vision)

        self.super_matrix, self.interaction_history = self.file_manager.load_state()
        self.extensions_queue = []
        self.pending_links = []
        self.actual_dir = "unknown"
        self.expanding = False

    """Acciones de los botones"""
    """Buttons actions"""

    def save_state(self):
        """Guarda el estado del programa y las interacciones"""
        """Save the state of the program and his interactions"""
        self.file_manager.save_state(self.super_matrix, self.interaction_history)
        
    def var_review(self, callback_act_ui):
        """Hace el bucle de revision de variables"""
        """It does the variable revision loop"""
        if not self.super_matrix:
            self.audio_service.read_text_interrupting("Primero debes capturar un programa para poder modificar sus variables.")
            return
            
        self.audio_service.read_text_interrupting("Iniciando el modo de repaso de variables.")
        variables = self.traducer.analize_matrix(self.super_matrix)
        answers = self._run_var_interaction(variables, review_mode=True)
        self.traducer.generate_code(self.super_matrix, self.code_dir, answers)
        self.save_state()
        self.audio_service.read_text("Variables modificadas. El código nuevo ya está generado.")
        callback_act_ui()

    def get_view_code(self):
        """Obtiene el codigo modificado en la vista"""
        """Gets the modified code from the view"""
        try:
            with open(self.code_dir, "r", encoding="utf-8") as file:
                code = file.read()
        except FileNotFoundError:
            return "# Archivo no generado de momento.", "Estado: Esperando captura...", [], False

        lines = code.split('\n')
        line_cut_fin = -1
        line_cut_ini = -1
        for i, line in enumerate(lines):
            if "# --- Sonido de inicialización ---" in line: line_cut_ini = i
            if "# --- Programa Principal ---" in line: 
                line_cut_fin = i
                break

        pitches_block = []
        if line_cut_ini != -1 and line_cut_fin != -1:
            visible_lines = []
            for i, line in enumerate(lines):
                if i < line_cut_ini: visible_lines.append(line)
                elif i >= line_cut_ini and i <= line_cut_fin: pitches_block.append(line)
                else: visible_lines.append(line)
            show_code = "\n".join(visible_lines)
        else:
            show_code = code

        state = "Estado: Código sin errores"
        error = False
        code_to_compile = show_code.replace('\xa0', ' ').replace('\t', '    ') + '\n'

        try:
            compile(code_to_compile, '<string>', 'exec')
        except SyntaxError as e:
            state = f"Error de Sintaxis en línea {e.lineno}"
            error = True

        return show_code, state, pitches_block, error

    def read_qrs(self, frame_bgr):
        """Lee los qrs que aparecen en la camara"""
        """It reads the QR's that appears on the camera"""
        if frame_bgr is None:
            self.audio_service.read_text("La cámara no está activa.")
            return
            
        temp_dir = os.path.join(self.workspace_dir, "outputs", "temp_read.jpg")
        self.vision.take_photo(frame_bgr, temp_dir)
        ordered_matrix = self.vision.get_command_matrix()
        
        text_to_read = []
        for row in ordered_matrix:
            for block in row:
                if block.strip() != "":
                    key = str(block).strip().lower()
                    info = self.traducer.symbols_table.get(key, {})
                    pronunciation = info.get("pronunciation", str(block))
                    text_to_read.append(pronunciation)
                    
        if text_to_read:
            self.audio_service.read_qrs(text_to_read)
        else:
            self.audio_service.read_text("No detecto ningún bloque en la pantalla.")

    def save_manual_code(self, new_code, pitches_block):
        """Guarda el codigo modificado manualmente"""
        """Save the code modified manually"""
        clean_code = new_code.replace('\xa0', ' ').replace('\t', '    ')
        return self.file_manager.save_edited_code(clean_code, pitches_block)

    def send_to_microbit(self):
        """Envia el codigo generado a la placa microbit"""
        """Sends the generated code to the Microbit board"""
        self.audio_service.read_text("Subiendo el programa a la placa Micro:bit.")
        exit, msg = self.file_manager.upload() 
        if not exit:
            self.audio_service.read_text_interrupting(msg)

    def ia_explain_code(self, callback_state):
        """Arranca un hilo para que la IA explique el codigo"""
        """Starts a thread for the IA to explain the code"""
        threading.Thread(target=lambda: self.ai_manager.explain_code(self.code_dir, callback_state), daemon=True).start()

    def change_tts(self, tts_modes, actual_idx):
        """Cambia el modo de tts usado para las variables de la placa"""
        """Change the TTS mode used for the variables on the board"""
        next_idx = (actual_idx + 1) % len(tts_modes)
        mode = tts_modes[next_idx]
        
        if self.traducer is not None:
            self.traducer.set_mode_tts(mode["value"])
            
        if mode["value"] == TTSMode.PC.value:
            self.audio_service.read_text("Modo de voz por ordenador activado.")
        elif mode["value"] == TTSMode.BOARD.value:
            self.audio_service.read_text("Modo de voz en la placa activado.")
        elif mode["value"] == TTSMode.SHUTDONW.value:
            self.audio_service.read_text("Voz de ejecución desactivada.")
            
        return next_idx, mode["texto"]

    def start_camera_hardware(self, idx, rotate=False):
        """Inicia el hardware de la camara"""
        """Starts camera hardware"""
        self.camera_thr.rotate = rotate
        self.camera_thr.start_hardware(idx)

    def pause_camera_hardware(self):
        """Pausa el hardware de la camara"""
        """Pauses camera hardware"""
        self.camera_thr.pause_hardware()

    def set_rotation_camera(self, rotate):
        """Modifica la rotacion de la camara"""
        """Changes the camera rotation"""
        self.camera_thr.rotate = rotate
        if rotate:
            self.audio_service.read_text_interrupting("Cámara en modo vertical.")
        else:
            self.audio_service.read_text_interrupting("Cámara en modo horizontal.")

    def free_camera_resources(self):
        """Libera los recursos de la camara"""
        """Frees all the camera resources"""
        self.camera_thr.free_all()

    def process_whole_frame(self, frame_bgr, img_dir, callback_act_ui):
        """Procesa el frame con los bloques para generar el codigo"""
        """Process the frame with the blocks to generate the code"""
        self.audio_service.read_text("Capturando.")
        self.vision.take_photo(frame_bgr, img_dir)
        spatial_matrix = self.vision.get_command_matrix()
        overflow = self.vision.check_overflow()
        
        if self.expanding:
            self.super_matrix = self._fuse_spatial_matrix(
                self.super_matrix, spatial_matrix, self.pending_links, self.actual_dir
            )
        else:
            self.super_matrix = spatial_matrix
            self.extensions_queue = []
            
        if overflow:
            if overflow.get("right"): self.extensions_queue.append(("side", overflow["right"]))
            if overflow.get("down"): self.extensions_queue.append(("bottom", overflow["down"]))

        self._process_next_extension(callback_act_ui)

    """Interacciones con las variables por voz"""
    """Interactions with the voice variables"""

    def _run_var_interaction(self, variables, review_mode):
        """Inicia y prepara el bucle de instanciacion y modificacion de variables"""
        """Starts and prepares the instantiation and modification of variables loop"""
        answers = []
        sim_memory = []
        history = self.interaction_history if review_mode else []
        review_index = 0
        
        for var in variables:
            type = var["type"]
            context = var["context"]
            
            if "var_" in context and sim_memory:
                context = re.sub(r'var_\d+', lambda m: sim_memory[-1], context)
            
            raw_answer = self._voice_interact(type, context, sim_memory, review_mode, history, review_index)
            
            is_var = (type != "assign_val")
            clean_ans = self.traducer.normalize_text(raw_answer, is_variable=is_var)
            
            if not review_mode:
                history.append(clean_ans)
            else:
                if review_index < len(history):
                    history[review_index] = clean_ans
                review_index += 1
                
            answers.append(clean_ans)
            
            if type == "declare_var":
                sim_memory.append(clean_ans)
                
        if not review_mode:
            self.interaction_history = history
        return answers

    def _voice_interact(self, block_type, context, var_memory, review_mode, history, review_index):
        """Hace las interacciones con el usuario para obtener los nombres y valores de las variables"""
        """Makes the interactions with the user to obtain the names and the values of the variables"""
        intro = f"Para {context}. " if context else ""
        if not self.voice_manager: return "0" if block_type == "assign_val" else "var"
        
        if review_mode and review_index < len(history):
            past_value = history[review_index]
            if block_type == "assign_val":
                self.audio_service.read_text(f"{intro}El valor actual es {past_value}. ¿Quieres modificarlo?")
            else:
                self.audio_service.read_text(f"{intro}El nombre actual es {past_value}. ¿Quieres modificarlo?")
                
            event = self.voice_manager.listen_dict_sync()
            modify = self._is_affirmative(event)
            
            if modify:
                question = "Dime el nuevo valor" if block_type == "assign_val" else "Dime el nuevo nombre"
                return self.voice_manager.voice_confirmation_loop(question, "0" if block_type == "assign_val" else "var")
            return past_value

        if block_type == "assign_val": return self.voice_manager.voice_confirmation_loop(f"{intro}Dime el valor", "0")
        if block_type == "declare_var": return self.voice_manager.voice_confirmation_loop(f"{intro}Dime el nombre de la variable", "var")
        if not var_memory: return self.voice_manager.voice_confirmation_loop(f"{intro}Dime el nombre de la variable", "var")
            
        last_var = var_memory[-1]
        self.audio_service.read_text(f"{intro}¿Quieres usar la última variable declarada, llamada {last_var}?")
        ans1 = self.voice_manager.listen_dict_sync()
        use_last = self._is_affirmative(ans1, ["claro", "correcto"])

        if use_last: return last_var

        if len(var_memory) > 1:
            self.audio_service.read_text("¿Quieres usar otra de las variables anteriores?")
            ans2 = self.voice_manager.listen_dict_sync()
            use_other = self._is_affirmative(ans2, ["claro", "correcto"])

            if use_other:
                while True:
                    self.audio_service.read_text("Dime el nombre de la variable para buscarla.")
                    search = self.voice_manager.listen_dict_sync()
                    if search.type == EventType.TAP:
                        self.audio_service.read_text("Por favor, dime el nombre hablando.")
                        continue
                    search_text = self.traducer.normalize_text(search.text, is_variable=True)
                    if "pasar" in search_text or "omitir" in search_text: return "var"
                    if search_text in var_memory: return search_text
                    self.audio_service.read_text("No he encontrado esa variable. Volvamos a intentarlo.")

        return self.voice_manager.voice_confirmation_loop(f"{intro}Dime el nombre", "var")

    def _is_affirmative(self, event, extra_words=None):
        """Determina si un evento representa una respuesta afirmativa"""
        """Determines if an event is an affirmative response"""
        words = ["sí", "si"] + (extra_words or [])
        return (
            (event.type == EventType.TAP and event.afirmative) or
            (event.type == EventType.VOICE and any(w in event.text for w in words)))
    
    """Funciones para la ampliacion de codigo"""
    """Functions to extend the code"""

    def _fuse_spatial_matrix(base_matrix, new_matrix, expected_nexus, dir="unknown"):
        """Toma dos matrices de bloques y las fusiona por los nexos y la dirección de desbordamiento"""
        """Takes two blocks matrices and fuse them together by the links and the overflow direction"""
        generics = ["valor_variable", "numero", "texto", "verdadero", "falso", "imagen"]
        strong_nexus = [n for n in expected_nexus if str(n).strip().lower() not in generics]
        anchors = strong_nexus if strong_nexus else expected_nexus
        
        new_super_matrix = [row.copy() for row in base_matrix]
        
        if dir == "side":
            mapped_rows_in_new = set()
            offset_c_global = 0 
            
            for nexus in anchors:
                nexus_str = str(nexus).strip().lower()
                r_base, c_base, r_new, c_new = -1, -1, -1, -1
                
                for r in range(len(new_super_matrix)):
                    for c in range(len(new_super_matrix[r])):
                        if str(new_super_matrix[r][c]).strip().lower() == nexus_str:
                            r_base, c_base = r, c
                            break
                    if r_base != -1: break
                
                for r in range(len(new_matrix)):
                    for c in range(len(new_matrix[r])):
                        if str(new_matrix[r][c]).strip().lower() == nexus_str:
                            r_new, c_new = r, c
                            break
                    if r_new != -1: break
                
                if r_base != -1 and r_new != -1:
                    mapped_rows_in_new.add(r_new)
                    offset_c_global = c_base - c_new
                    
                    for c in range(c_new + 1, len(new_matrix[r_new])):
                        val = new_matrix[r_new][c]
                        target_c = c + offset_c_global
                        while len(new_super_matrix[r_base]) <= target_c:
                            new_super_matrix[r_base].append("")
                        if val != "":
                            new_super_matrix[r_base][target_c] = val
                            
            if mapped_rows_in_new:
                max_mapped_r = max(mapped_rows_in_new)
                for r in range(max_mapped_r + 1, len(new_matrix)):
                    new_row = []
                    for c in range(len(new_matrix[r])):
                        val = new_matrix[r][c]
                        target_c = c + offset_c_global
                        if target_c >= 0:
                            while len(new_row) <= target_c:
                                new_row.append("")
                            if val != "":
                                new_row[target_c] = val
                    new_super_matrix.append(new_row)
            else:
                for r in range(len(new_matrix)):
                    new_super_matrix.append(new_matrix[r])
                    
        elif dir == "bottom":
            base_anchor_r, c_base = -1, -1
            new_anchor_r, c_new = -1, -1
            used_nexus = None
            
            for nexus in anchors:
                nexus_str = str(nexus).strip().lower()
                for r in range(len(new_super_matrix)-1, -1, -1):
                    for c in range(len(new_super_matrix[r])):
                        if str(new_super_matrix[r][c]).strip().lower() == nexus_str:
                            base_anchor_r, c_base = r, c
                            break
                    if base_anchor_r != -1: break
                
                for r in range(len(new_matrix)):
                    for c in range(len(new_matrix[r])):
                        if str(new_matrix[r][c]).strip().lower() == nexus_str:
                            new_anchor_r, c_new = r, c
                            break
                    if new_anchor_r != -1: break
                
                if base_anchor_r != -1 and new_anchor_r != -1:
                    used_nexus = nexus
                    break
            
            if used_nexus:
                offset_c = c_base - c_new
                
                for c in range(c_new + 1, len(new_matrix[new_anchor_r])):
                    val = new_matrix[new_anchor_r][c]
                    target_c = c + offset_c
                    while len(new_super_matrix[base_anchor_r]) <= target_c:
                        new_super_matrix[base_anchor_r].append("")
                    if val != "":
                        new_super_matrix[base_anchor_r][target_c] = val
                
                for r in range(new_anchor_r + 1, len(new_matrix)):
                    new_row = []
                    for c in range(len(new_matrix[r])):
                        val = new_matrix[r][c]
                        target_c = c + offset_c
                        if target_c >= 0:
                            while len(new_row) <= target_c:
                                new_row.append("")
                            if val != "":
                                new_row[target_c] = val
                    new_super_matrix.append(new_row)
            else:
                for r in range(len(new_matrix)):
                    new_super_matrix.append(new_matrix[r])
        else:
            for r in range(len(new_matrix)):
                new_super_matrix.append(new_matrix[r])
                
        return new_super_matrix

    def _process_next_extension(self, callback_act_ui):
        """Procesa la siguiente extension en caso de haberla, si no, genera el codigo"""
        """Process the next extension in case it exists, if not, it generates the code"""
        if not self.extensions_queue:
            self._finalize_and_generate(callback_act_ui)
            return

        dir, links = self.extensions_queue.pop(0)
        self.actual_dir = dir
        self.pending_links = links

        names_pronunciation = []
        for n in links:
            pronunciation = self.traducer.tabla_simbolos.get(n.lower(), {}).get("pronunciation", n)
            if pronunciation not in names_pronunciation: names_pronunciation.append(pronunciation)
                
        names_str = ", y ".join(names_pronunciation)

        if self.voice_manager is not None:
            answer = self.voice_manager.voice_confirmation_loop(
                f"El bloque {names_str} toca el borde {dir}. ¿Quieres ampliar el programa haciendo otra foto?",
                open_question=False
            )
            if "sí" in answer or "si" in answer:
                self.expanding = True
                self.audio_service.read_text(f"De acuerdo. Pon el bloque {names_str} en la nueva foto para usarlo de referencia. Pulsa capturar cuando estés listo.")
                return 
            else:
                self.audio_service.read_text("De acuerdo, cancelando el resto de ampliaciones y procesando el programa.")
                self.extensions_queue.clear()
                
        self._finalize_and_generate(callback_act_ui)

    def _finalize_and_generate(self, callback_act_ui):
        """Finaliza y genera el codigo"""
        """Finalize and generate the code"""
        self.expanding = False
        variables = self.traducer.analize_matrix(self.super_matrix)
        answers = self._run_var_interaction(variables, review_mode=False)
        self.traducer.generate_code(self.super_matrix, self.code_dir, answers) 
        self.save_state()
        self.audio_service.read_text("El código nuevo ya está generado.")
        callback_act_ui()