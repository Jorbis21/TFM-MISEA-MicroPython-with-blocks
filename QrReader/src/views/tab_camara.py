import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QFrame, QSplitter, QComboBox, QSizePolicy)
from PyQt6.QtGui import (QImage, QPixmap, QIcon)
from PyQt6.QtCore import Qt, QTimer, QSize
from views.highlighter import PythonHighlighter
from utils.constants import TTSMode
from utils.strings import t

class TabCamara(QWidget):

    def __init__(self, workspace_dir, assets_dir, camera_ctrl, program_builder, audio_service):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.icons_dir = os.path.join(assets_dir, "icons")
        self.img_dir = os.path.join(self.workspace_dir, "inputs", "program.jpg")
        
        self.ctrl = camera_ctrl
        self.program = program_builder
        self.audio = audio_service

        self.edit_mode = False
        self.rotate_camera = False
        self.shutdown_camera = False
        self.highcontrast_mode = True
        self.clicks = 0
        self.last_key = None
        self.click_timer = None
        
        self.actual_qr_texts = []
        self._ia_explaining = False
        self.pitches_block = []
        self.frame_actual_bgr = None

        # Anuncio por voz del numero de bloques detectados, con estabilizacion:
        # solo avisa cuando el numero deja de cambiar durante QR_COUNT_DEBOUNCE_MS,
        # para no saturar al usuario mientras coloca varios bloques seguidos.
        # Voice announcement of the number of detected blocks, debounced:
        # only announces once the number stops changing for QR_COUNT_DEBOUNCE_MS,
        # so the user isn't overwhelmed while placing several blocks in a row.
        self.QR_COUNT_DEBOUNCE_MS = 1500
        self._last_seen_qr_count = 0
        self._last_announced_qr_count = 0
        self._qr_count_timer = QTimer()
        self._qr_count_timer.setSingleShot(True)
        self._qr_count_timer.timeout.connect(self._announce_qr_count)

        self.ctrl.camera_thr.new_frame.connect(self.update_frame)

        self._setup_ui()
        self.read_generated_code()
        self.resume_camera()

    def _setup_ui(self):
        """Monta la interfaz"""
        """Setup the interface"""
        main_layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        btns_layout = QHBoxLayout()
        
        self.capture_btn = QPushButton(t("btn_capture"))
        self.capture_btn.setObjectName("capture_btn")
        self.capture_btn.clicked.connect(self.action_capture)
        btns_layout.addWidget(self.capture_btn)
        
        self.send_btn = QPushButton(t("btn_send"))
        self.send_btn.setObjectName("send_btn")
        self.send_btn.clicked.connect(self.action_send)
        btns_layout.addWidget(self.send_btn)

        self.ia_btn = QPushButton(t("btn_explain"))
        self.ia_btn.setObjectName("ia_btn")
        self.ia_btn.clicked.connect(self.action_ia_explain)
        btns_layout.addWidget(self.ia_btn)

        self.read_btn = QPushButton(t("btn_read"))
        self.read_btn.setObjectName("read_btn")
        self.read_btn.clicked.connect(self.action_read_qrs)
        btns_layout.addWidget(self.read_btn)

        self.tts_modes = [
            {"text": t("tts_mode_pc"), "value": TTSMode.PC.value},
            {"text": t("tts_mode_board"), "value": TTSMode.BOARD.value},
            {"text": t("tts_mode_off"), "value": TTSMode.SHUTDONW.value}
        ]
        self.idx_tts = 0
        self.tts_btn = QPushButton(self.tts_modes[self.idx_tts]["text"])
        self.tts_btn.setObjectName("tts_btn")
        self.tts_btn.clicked.connect(self.action_change_tts)
        btns_layout.addWidget(self.tts_btn)

        self.review_btn = QPushButton(t("btn_review"))
        self.review_btn.setObjectName("review_btn")
        self.review_btn.clicked.connect(self.action_var_review)
        btns_layout.addWidget(self.review_btn)

        left_layout.addLayout(btns_layout)

        self.text_box = QTextEdit()
        self.text_box.setObjectName("text_box")
        self.text_box.setReadOnly(True)
        
        self.highlighter = PythonHighlighter(self.text_box.document())
        left_layout.addWidget(self.text_box)

        layout_overlay_text = QVBoxLayout(self.text_box)
        layout_overlay_text.setContentsMargins(10, 10, 25, 15) 
        layout_overlay_text.addStretch() 
        
        layout_h_text = QHBoxLayout()
        layout_h_text.addStretch() 
        
        self.edit_btn = QPushButton()
        self.edit_btn.setObjectName("edit_btn")
        self.edit_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "edit_cont.png")))
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self.action_edit_code)
        
        layout_h_text.addWidget(self.edit_btn)
        layout_overlay_text.addLayout(layout_h_text)

        self.status_label = QLabel(t("status_camera_active"))
        self.status_label.setObjectName("status_label")
        left_layout.addWidget(self.status_label)

        self.splitter.addWidget(left_panel)

        self.video_label = QLabel()
        self.video_label.setObjectName("video_label")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_label.setMinimumSize(400, 300) 

        layout_overlay = QVBoxLayout(self.video_label)
        layout_overlay.setContentsMargins(15, 15, 15, 15)
        
        layout_btns_camera = QHBoxLayout()
        layout_btns_camera.setSpacing(10)
        layout_btns_camera.addStretch()

        self.rotate_btn = QPushButton()
        self.rotate_btn.setObjectName("overlay_btn")
        self.shutdown_btn = QPushButton()
        self.shutdown_btn.setObjectName("overlay_btn")

        self.rotate_btn.setIcon(QIcon(os.path.join(self.icons_dir, "sync_cont.png")))
        self.shutdown_btn.setIcon(QIcon(os.path.join(self.icons_dir, "on-off-button_cont.png")))

        icon_size = QSize(24, 24)
        self.rotate_btn.setIconSize(icon_size)
        self.shutdown_btn.setIconSize(icon_size)

        self.shutdown_btn.clicked.connect(self.action_shutdown_camera)
        self.rotate_btn.clicked.connect(self.action_rotate_camera)

        self.combo_cameras = QComboBox()
        self.combo_cameras.setObjectName("combo_cameras")
        self.combo_cameras.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        real_cameras = self.ctrl.detect_cameras()
        for cam_id in real_cameras:
            name = t("camera_main") if cam_id == 0 else t("camera_secondary", idx=cam_id)
            self.combo_cameras.addItem(name, userData=cam_id)
            
        if len(real_cameras) <= 1:
            self.combo_cameras.hide()
            
        self.combo_cameras.currentIndexChanged.connect(self.accion_cambiar_camara)

        layout_btns_camera.addWidget(self.rotate_btn)
        layout_btns_camera.addWidget(self.shutdown_btn)
        layout_btns_camera.addWidget(self.combo_cameras)
        layout_btns_camera.addStretch()

        layout_overlay.addLayout(layout_btns_camera)
        layout_overlay.addStretch()
        
        self.splitter.addWidget(self.video_label)
        self.splitter.setSizes([640, 640])

    def _process_simple_click(self, text):
        """Procesa el click simple del teclado"""
        """Process the simple click of the keyboard"""
        self.clicks = 0
        self.last_key = None
        self.audio.read_text(text)
            
    def _process_double_click(self, func):
        """Ejecuta la accion"""
        """Executes the action"""
        func()

    def update_frame(self, frame_bgr, frame_rgb, texts):
        """Actualiza el frame de la camara"""
        """Updates the camera frame"""
        if frame_rgb is not None:
            self.frame_actual_bgr = frame_bgr
            self.actual_qr_texts = texts
            
            height, width, chanels = frame_rgb.shape
            line_bytes = chanels * width
            img_qt = QImage(frame_rgb.data, width, height, line_bytes, QImage.Format.Format_RGB888)
            
            pixmap = QPixmap.fromImage(img_qt)
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.width(), self.video_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))

            current_count = len(texts) if texts else 0
            if current_count != self._last_seen_qr_count:
                self._last_seen_qr_count = current_count
                self._qr_count_timer.start(self.QR_COUNT_DEBOUNCE_MS)

    def _announce_qr_count(self):
        """Anuncia el numero de bloques detectados, una vez que se ha estabilizado"""
        """Announces the number of detected blocks, once it has stabilized"""
        if self.program.voice_manager and self.program.voice_manager.dictation_mode:
            self._last_announced_qr_count = self._last_seen_qr_count
            return

        count = self._last_seen_qr_count
        if count == self._last_announced_qr_count:
            return
        self._last_announced_qr_count = count

        if count == 0:
            self.audio.read_text(t("no_blocks_detected"))
        elif count == 1:
            self.audio.read_text(t("qr_count_singular", count=count))
        else:
            self.audio.read_text(t("qr_count_plural", count=count))

    def _stop_qr_count_tracking(self):
        """Detiene el temporizador de estabilizacion y olvida el ultimo recuento visto, para que no dispare un aviso fuera de lugar cuando la camara deje de ver frames"""
        """Stops the stabilization timer and forgets the last seen count, so it can't fire a stray announcement once the camera stops seeing frames"""
        self._qr_count_timer.stop()
        self._last_seen_qr_count = self._last_announced_qr_count

    def process_chortcut(self, tecla_id, text, func):
        """Procesa el atajo del teclado para hacer la lectura o la ejecucion"""
        """Process the keyboard shortcut to make the reading or the action"""
        if self.edit_mode: return 
        if self.last_key != tecla_id:
            if self.click_timer is not None and self.click_timer.isActive(): 
                self.click_timer.stop()
            self.clicks = 0
            self.last_key = tecla_id
            
        self.clicks += 1
        if self.clicks == 1:
            self.click_timer = QTimer()
            self.click_timer.setSingleShot(True)
            self.click_timer.timeout.connect(lambda: self._process_simple_click(text))
            self.click_timer.start(400)
        elif self.clicks == 2:
            if self.click_timer is not None and self.click_timer.isActive(): 
                self.click_timer.stop()
            self._process_double_click(func)
            self.clicks = 0
            self.last_key = None

    def update_icons(self, highcontrast_mode):
        """Actualiza los iconos dependiendo del tema"""
        """Updates the icons depending on the theme"""
        self.highcontrast_mode = highcontrast_mode
        if highcontrast_mode:
            edit_icon_dir = os.path.join(self.icons_dir, "edit_cont.png")
            rotate_icon_dir = os.path.join(self.icons_dir, "sync_cont.png")
            shutdown_icon_dir = os.path.join(self.icons_dir, "on-off-button_cont.png")
        else:
            edit_icon_dir = os.path.join(self.icons_dir, "edit.png")
            rotate_icon_dir = os.path.join(self.icons_dir, "sync.png")
            shutdown_icon_dir = os.path.join(self.icons_dir, "on-off-button.png")
            
        self.edit_btn.setIcon(QIcon(edit_icon_dir))
        self.rotate_btn.setIcon(QIcon(rotate_icon_dir))
        self.shutdown_btn.setIcon(QIcon(shutdown_icon_dir))

    def action_capture(self):
        """Accion de captura de imagen"""
        """Capture image action"""
        if self.frame_actual_bgr is None: return
        self.program.process_whole_frame(self.frame_actual_bgr, self.img_dir, self.read_generated_code)

    def action_var_review(self):
        """Accion de revision de variables"""
        """Variable review action"""
        self.program.var_review(self.read_generated_code)

    def action_send(self):
        """Accion de enviar el codigo a la placa"""
        """Code send action to the board"""
        self.program.send_to_microbit()

    def action_ia_explain(self):
        """Accion de explicacion por IA"""
        """IA explanation action"""
        # Guardia contra doble pulsacion con una bandera propia, NO con
        # setEnabled(False): deshabilitar un boton que tiene el foco hace que
        # Qt mueva el foco al siguiente widget automaticamente, y el lector
        # de foco de accesibilidad (_on_focus_changed en app_window.py)
        # anuncia ese otro boton en voz alta - aqui, "Leer QRs", el siguiente
        # en la fila, sin que nadie lo haya pulsado.
        # Guard against double-clicking with our own flag, NOT setEnabled(False):
        # disabling a button that has focus makes Qt shift focus to the next
        # widget automatically, and the accessibility focus reader
        # (_on_focus_changed in app_window.py) announces that other button out
        # loud - here, "Read QRs", the next one in line, without anyone having
        # clicked it.
        if self._ia_explaining:
            return
        self._ia_explaining = True

        def update_state(text, color=None):
            self.status_label.setText(text)
            if color:
                self.status_label.setStyleSheet(f"color: {color};")

        def on_finished():
            self._ia_explaining = False

        self.program.ia_explain_code(update_state, on_finished)

    def action_change_tts(self):
        """Accion de cambio de modo de TTS"""
        """Change TTS mode action"""
        self.idx_tts, button_text = self.program.change_tts(self.tts_modes, self.idx_tts)
        self.tts_btn.setText(button_text)

    def action_read_qrs(self):
        """Accion de leer los QR's"""
        """Read QR's action"""
        self.program.read_qrs(self.frame_actual_bgr)

    def read_generated_code(self):
        """Lectura del codigo generado para la comprobacion de errores"""
        """Generated code reading for checking errors"""
        self.text_box.clear()
        show_code, state, self.pitches_block, error = self.program.get_view_code()
        self.text_box.setPlainText(show_code)
        self.status_label.setText(state)
        
        if error:
            self.audio.read_text(t("error_syntax_audio"))

    def action_edit_code(self):
        """Accion de editar el codigo por teclado"""
        """Code editing action by keyboard"""
        if not self.edit_mode:
            self.edit_mode = True
            if self.highcontrast_mode:
                self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "diskette_cont.png")))
            else:
                self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "diskette.png")))
            self.text_box.setReadOnly(False)
            self.status_label.setText(t("status_edit_mode"))
        else:
            new_code = self.text_box.toPlainText()
            success, error = self.program.save_manual_code(new_code, self.pitches_block)
            
            if success:
                self.edit_mode = False
                if self.highcontrast_mode:
                    self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "edit_cont.png")))
                else:
                    self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
                self.text_box.setReadOnly(True)
                self.read_generated_code()
            else:
                self.status_label.setText(t("status_save_error", error=error))

    def action_save_shortcut(self):
        """Accion para guardar el codigo modificado"""
        """Modified code save action"""
        if self.edit_mode:
            new_code = self.text_box.toPlainText()
            success, _ = self.program.save_manual_code(new_code, self.pitches_block)
            if success:
                self.edit_mode = False
                self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
                self.text_box.setReadOnly(True)
                self.read_generated_code()
                self.status_label.setText(t("status_quick_save"))

    def action_rotate_camera(self):
        """Accion para rotar la camara"""
        """Camera rotate action"""
        self.rotate_camera = not self.rotate_camera
        self.ctrl.set_rotation_camera(self.rotate_camera)

    def action_shutdown_camera(self):
        """Accion para apagar la camara"""
        """Shutdown camera action"""
        self.shutdown_camera = not self.shutdown_camera
        if self.shutdown_camera:
            self.ctrl.pause_camera_hardware()
            self._stop_qr_count_tracking()
            
            self.video_label.clear()
            self.video_label.setStyleSheet("background-color: black;")
            
            self.status_label.setText(t("status_camera_off"))
        else:
            self.video_label.setStyleSheet("")
            idx = self.combo_cameras.currentData()
            self.ctrl.start_camera_hardware(idx, self.rotate_camera)
            self.status_label.setText(t("status_camera_active"))

    def accion_cambiar_camara(self, index):
        """Accion de cambiar la camara"""
        """Change camera action"""
        if not self.shutdown_camera:
            self.ctrl.pause_camera_hardware()
            self._stop_qr_count_tracking()
            self.video_label.clear() 
            real_id = self.combo_cameras.itemData(index)
            self.ctrl.start_camera_hardware(real_id, self.rotate_camera)

    def cleanup(self):
        """Limpia los recursos de la camara"""
        """Cleans the camera resources"""
        self._stop_qr_count_tracking()
        self.ctrl.free_camera_resources()

    def pause_camera(self):
        """Pausa la camara"""
        """Pause the camera"""
        self.ctrl.pause_camera_hardware()
        self._stop_qr_count_tracking()
        self.video_label.clear()
        self.video_label.setStyleSheet("background-color: black;")

    def resume_camera(self):
        """Reinicia la camara"""
        """Resume the camera"""
        if not self.shutdown_camera:
            self.video_label.setStyleSheet("")
            idx = self.combo_cameras.currentData()
            self.ctrl.start_camera_hardware(idx, self.rotate_camera)