import threading, re, os
from utils.constants import TTSMode, EventType
from utils.main_thread import run_on_main_thread
from utils.strings import t


class ProgramBuilder:

    """
        Construye el programa a partir de lo que ve la camara: fusiona fotos
        cuando el programa no cabe en una sola, gestiona la interaccion por voz
        para nombrar y asignar variables, y orquesta la generacion, guardado,
        explicacion y envio del codigo.
    """
    """
        Builds the program from what the camera sees: fuses photos when the
        program doesn't fit in a single one, manages the voice interaction to
        name and assign variables, and orchestrates the generation, saving,
        explanation and sending of the code.
    """

    def __init__(self, workspace_dir, code_dir, traducer, code_manager, audio_service, vision, ai_manager, voice_manager):
        self.workspace_dir = workspace_dir
        self.code_dir = code_dir
        self.traducer = traducer
        self.code_manager = code_manager
        self.audio_service = audio_service
        self.vision = vision
        self.ai_manager = ai_manager
        self.voice_manager = voice_manager

        self.super_matrix, self.interaction_history, load_error = self.code_manager.load_state()
        if load_error:
            self.audio_service.read_text(t("warn_load_state_failed"))

        self.extensions_queue = []
        self.pending_links = []
        self.actual_dir = "unknown"
        self.expanding = False

    """Acciones de los botones"""
    """Buttons actions"""

    def save_state(self):
        """Guarda el estado del programa y las interacciones"""
        """Save the state of the program and his interactions"""
        success, error = self.code_manager.save_state(self.super_matrix, self.interaction_history)
        if not success:
            self.audio_service.read_text_interrupting(t("warn_save_state_failed"))

    def var_review(self, callback_act_ui):
        """Hace el bucle de revision de variables"""
        """It does the variable revision loop"""
        if not self.super_matrix:
            self.audio_service.read_text_interrupting(t("need_capture_first"))
            return

        self.audio_service.read_text_interrupting(t("starting_var_review"))
        variables = self.traducer.analize_matrix(self.super_matrix)
        answers = self._run_var_interaction(variables, review_mode=True)
        self.traducer.generate_code(self.super_matrix, self.code_dir, answers)
        self.save_state()
        self.audio_service.read_text(t("vars_modified"))
        callback_act_ui()

    def get_view_code(self):
        """Obtiene el codigo tal como debe mostrarse en el editor"""
        """Gets the code as it should be displayed in the editor"""
        return self.code_manager.get_display_code()

    def read_qrs(self, frame_bgr):
        """Lee los qrs que aparecen en la camara"""
        """It reads the QR's that appears on the camera"""
        if frame_bgr is None:
            self.audio_service.read_text(t("camera_not_active"))
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
            self.audio_service.read_text(t("no_blocks_detected"))

    def save_manual_code(self, new_code, pitches_block):
        """Guarda el codigo modificado manualmente"""
        """Save the code modified manually"""
        return self.code_manager.save_manual_code(new_code, pitches_block)

    def send_to_microbit(self):
        """Envia el codigo generado a la placa microbit"""
        """Sends the generated code to the Microbit board"""
        self.audio_service.read_text(t("uploading_to_board"))
        success, msg = self.code_manager.upload()
        if not success:
            self.audio_service.read_text_interrupting(msg)

    def ia_explain_code(self, callback_state, on_finished=None):
        """Arranca un hilo para que la IA explique el codigo"""
        """Starts a thread for the IA to explain the code"""
        code = self.code_manager.read_code()
        if code is None:
            self.audio_service.read_text(t("no_program_generated"))
            if on_finished:
                on_finished()
            return

        safe_callback = lambda *args: run_on_main_thread(callback_state, *args)

        def _task():
            try:
                self.ai_manager.explain_code(code, safe_callback)
            finally:
                if on_finished:
                    run_on_main_thread(on_finished)

        threading.Thread(target=_task, daemon=True).start()

    def change_tts(self, tts_modes, actual_idx):
        """Cambia el modo de tts usado para las variables de la placa"""
        """Change the TTS mode used for the variables on the board"""
        next_idx = (actual_idx + 1) % len(tts_modes)
        mode = tts_modes[next_idx]

        if self.traducer is not None:
            self.traducer.set_mode_tts(mode["value"])

        if mode["value"] == TTSMode.PC.value:
            self.audio_service.read_text(t("tts_mode_pc_on"))
        elif mode["value"] == TTSMode.BOARD.value:
            self.audio_service.read_text(t("tts_mode_board_on"))
        elif mode["value"] == TTSMode.SHUTDONW.value:
            self.audio_service.read_text(t("tts_mode_off_on"))

        return next_idx, mode["text"]

    def process_whole_frame(self, frame_bgr, img_dir, callback_act_ui):
        """Procesa el frame con los bloques para generar el codigo"""
        """Process the frame with the blocks to generate the code"""
        self.audio_service.read_text(t("capturing"))
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
                self.audio_service.read_text(t("ask_modify_value", intro=intro, value=past_value))
            else:
                self.audio_service.read_text(t("ask_modify_name", intro=intro, value=past_value))

            event = self.voice_manager.listen_dict_sync()
            modify = self._is_affirmative(event)

            if modify:
                question = t("ask_new_value") if block_type == "assign_val" else t("ask_new_name")
                return self.voice_manager.voice_confirmation_loop(question, "0" if block_type == "assign_val" else "var")
            return past_value

        if block_type == "assign_val": return self.voice_manager.voice_confirmation_loop(t("ask_value", intro=intro), "0")
        if block_type == "declare_var": return self.voice_manager.voice_confirmation_loop(t("ask_var_name", intro=intro), "var")
        if not var_memory: return self.voice_manager.voice_confirmation_loop(t("ask_var_name", intro=intro), "var")

        last_var = var_memory[-1]
        self.audio_service.read_text(t("ask_use_last_var", intro=intro, name=last_var))
        ans1 = self.voice_manager.listen_dict_sync()
        use_last = self._is_affirmative(ans1, t("kw_casual_yes"))

        if use_last: return last_var

        if len(var_memory) > 1:
            self.audio_service.read_text(t("ask_use_other_var"))
            ans2 = self.voice_manager.listen_dict_sync()
            use_other = self._is_affirmative(ans2, t("kw_casual_yes"))

            if use_other:
                while True:
                    self.audio_service.read_text(t("ask_search_var_name"))
                    search = self.voice_manager.listen_dict_sync()
                    if search.type == EventType.TAP:
                        self.audio_service.read_text(t("please_speak_name"))
                        continue
                    search_text = self.traducer.normalize_text(search.text, is_variable=True)
                    if self._contains_word(search_text, set(t("kw_skip"))): return "var"
                    if search_text in var_memory: return search_text
                    self.audio_service.read_text(t("var_not_found"))

        return self.voice_manager.voice_confirmation_loop(t("ask_name", intro=intro), "var")

    @staticmethod
    def _contains_word(text, words):
        """Comprueba si alguna de las palabras aparece como palabra completa en el texto, para que 'así' no se confunda con 'sí'"""
        """Checks if any of the words appears as a whole word in the text, so 'así' isn't mistaken for 'sí'"""
        tokens = re.findall(r"[\wáéíóúñ]+", text.lower())
        return any(t in words for t in tokens)

    def _is_affirmative(self, event, extra_words=None):
        """Determina si un evento representa una respuesta afirmativa"""
        """Determines if an event is an affirmative response"""
        words = set(t("kw_yes")) | set(extra_words or [])
        return (
            (event.type == EventType.TAP and event.afirmative) or
            (event.type == EventType.VOICE and self._contains_word(event.text, words)))

    """Funciones para la ampliacion de codigo"""
    """Functions to extend the code"""

    @staticmethod
    def _fuse_spatial_matrix(base_matrix, new_matrix, expected_nexus, dir="unknown"):
        """Toma dos matrices de bloques y las fusiona por los nexos y la dirección de desbordamiento"""
        """Takes two blocks matrices and fuse them together by the links and the overflow direction"""
        generics = [
            t("generic_declare_var_key"), t("generic_reference_var_key"), t("generic_assign_val_key"),
            t("generic_number_key"), "texto", t("generic_true_key"), t("generic_false_key"), "imagen"
        ]
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
            pronunciation = self.traducer.symbols_table.get(n.lower(), {}).get("pronunciation", n)
            if pronunciation not in names_pronunciation: names_pronunciation.append(pronunciation)

        names_str = t("list_join_and").join(names_pronunciation)

        if self.voice_manager is not None:
            dir_word = t("dir_side") if dir == "side" else t("dir_bottom") if dir == "bottom" else dir
            wants_expand = self.voice_manager.confirm_yes_no(
                t("ask_expand_program", names=names_str, dir=dir_word)
            )
            if wants_expand:
                self.expanding = True
                self.audio_service.read_text(t("ok_expand_photo", names=names_str))
                return
            else:
                self.audio_service.read_text(t("ok_cancel_expand"))
                # Ya no se vacia toda la cola: rechazar una direccion (p.ej.
                # "a la derecha") no debe impedir que se pregunte tambien por
                # la otra (p.ej. "por abajo") si tambien estaba pendiente.
                # The whole queue no longer gets cleared: declining one
                # direction (e.g. "to the right") shouldn't prevent also
                # asking about the other (e.g. "downward") if it was also
                # pending.
                self._process_next_extension(callback_act_ui)
                return

        self._finalize_and_generate(callback_act_ui)

    def _finalize_and_generate(self, callback_act_ui):
        """Finaliza y genera el codigo"""
        """Finalize and generate the code"""
        self.expanding = False
        variables = self.traducer.analize_matrix(self.super_matrix)
        answers = self._run_var_interaction(variables, review_mode=False)
        self.traducer.generate_code(self.super_matrix, self.code_dir, answers)
        self.save_state()
        self.audio_service.read_text(t("code_generated"))
        callback_act_ui()