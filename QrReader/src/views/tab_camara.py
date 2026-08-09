import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QFrame, QSplitter, QComboBox, QSizePolicy)
from PyQt6.QtGui import (QImage, QPixmap, QIcon)
from PyQt6.QtCore import Qt, QTimer, QSize
from views.highlighter import PythonHighlighter
from utils.constants import TTSMode

class TabCamara(QWidget):

    def __init__(self, workspace_dir, assets_dir, camera_ctrl):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.icons_dir = os.path.join(assets_dir, "icons")
        self.img_dir = os.path.join(self.workspace_dir, "inputs", "program.jpg")
        
        self.ctrl = camera_ctrl

        self.edit_mode = False
        self.rotate_camera = False
        self.shutdown_camera = False
        self.highcontrast_mode = True
        self.clicks = 0
        self.last_key = None
        self.click_timer = None
        
        self.actual_qr_texts = []
        self.pitches_block = []
        self.frame_actual_bgr = None

        
        self.ctrl.camera_thr.new_frame.connect(self.update_frame)

        self._setup_ui()
        self.read_generated_code()
        self.resume_camera()

    """"""""""""""""""""""""
    def _setup_ui(self):
        layout_principal = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_principal.addWidget(self.splitter)

        panel_izquierdo = QFrame()
        layout_izq = QVBoxLayout(panel_izquierdo)
        layout_botones = QHBoxLayout()
        
        self.btn_capturar = QPushButton("Tomar Foto")
        self.btn_capturar.setObjectName("btn_capturar")
        self.btn_capturar.clicked.connect(self.action_capture)
        layout_botones.addWidget(self.btn_capturar)
        
        self.btn_enviar = QPushButton("Enviar a MicroBit")
        self.btn_enviar.setObjectName("btn_enviar")
        self.btn_enviar.clicked.connect(self.action_send)
        layout_botones.addWidget(self.btn_enviar)

        self.btn_ia = QPushButton("Explicar con IA")
        self.btn_ia.setObjectName("btn_ia")
        self.btn_ia.clicked.connect(self.action_ia_explain)
        layout_botones.addWidget(self.btn_ia)

        self.btn_leer = QPushButton("Leer QRs")
        self.btn_leer.setObjectName("btn_leer")
        self.btn_leer.clicked.connect(self.action_read_qrs)
        layout_botones.addWidget(self.btn_leer)

        self.modos_tts = [
            {"text": "Voz: PC", "value": TTSMode.PC.value},
            {"text": "Voz: Placa", "value": TTSMode.BOARD.value},
            {"text": "Voz: Apagada", "value": TTSMode.SHUTDONW.value}
        ]
        self.idx_tts = 0
        self.btn_tts = QPushButton(self.modos_tts[self.idx_tts]["texto"])
        self.btn_tts.setObjectName("btn_tts")
        self.btn_tts.clicked.connect(self.action_change_tts)
        layout_botones.addWidget(self.btn_tts)

        self.btn_repaso = QPushButton("Modificar Variables")
        self.btn_repaso.setObjectName("btn_repaso")
        self.btn_repaso.clicked.connect(self.action_var_review)
        layout_botones.addWidget(self.btn_repaso)

        layout_izq.addLayout(layout_botones)

        self.caja_texto = QTextEdit()
        self.caja_texto.setObjectName("caja_texto")
        self.caja_texto.setReadOnly(True)
        
        self.highlighter = PythonHighlighter(self.caja_texto.document())
        layout_izq.addWidget(self.caja_texto)

        layout_overlay_texto = QVBoxLayout(self.caja_texto)
        layout_overlay_texto.setContentsMargins(10, 10, 25, 15) 
        layout_overlay_texto.addStretch() 
        
        layout_h_texto = QHBoxLayout()
        layout_h_texto.addStretch() 
        
        self.edit_btn = QPushButton()
        self.edit_btn.setObjectName("edit_btn")
        self.edit_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ruta_icono_editar = os.path.join(self.icons_dir, "edit_cont.png")
        self.edit_btn.setIcon(QIcon(ruta_icono_editar))
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self.action_edit_code)
        
        layout_h_texto.addWidget(self.edit_btn)
        layout_overlay_texto.addLayout(layout_h_texto)

        self.status_label = QLabel("Estado: Cámara Activa")
        self.status_label.setObjectName("status_label")
        layout_izq.addWidget(self.status_label)

        self.splitter.addWidget(panel_izquierdo)

        self.video_label = QLabel()
        self.video_label.setObjectName("video_label")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_label.setMinimumSize(400, 300) 

        layout_overlay = QVBoxLayout(self.video_label)
        layout_overlay.setContentsMargins(15, 15, 15, 15)
        
        layout_botones_camara = QHBoxLayout()
        layout_botones_camara.setSpacing(10)
        layout_botones_camara.addStretch()

        self.rotate_btn = QPushButton()
        self.rotate_btn.setObjectName("overlay_btn")
        self.shutdown_btn = QPushButton()
        self.shutdown_btn.setObjectName("overlay_btn")

        self.rotate_btn.setIcon(QIcon(os.path.join(self.icons_dir, "sync_cont.png")))
        self.shutdown_btn.setIcon(QIcon(os.path.join(self.icons_dir, "on-off-button_cont.png")))

        tamano_icono = QSize(24, 24)
        self.rotate_btn.setIconSize(tamano_icono)
        self.shutdown_btn.setIconSize(tamano_icono)

        self.shutdown_btn.clicked.connect(self.accion_apagar_camara)
        self.rotate_btn.clicked.connect(self.accion_rotar_camara)

        self.combo_cameras = QComboBox()
        self.combo_cameras.setObjectName("combo_cameras")
        self.combo_cameras.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        camaras_reales = self.ctrl.detect_cameras()
        for cam_id in camaras_reales:
            nombre = "Cámara Principal" if cam_id == 0 else f"Cámara Secundaria ({cam_id})"
            self.combo_cameras.addItem(nombre, userData=cam_id)
            
        if len(camaras_reales) <= 1:
            self.combo_cameras.hide()
            
        self.combo_cameras.currentIndexChanged.connect(self.accion_cambiar_camara)

        layout_botones_camara.addWidget(self.rotate_btn)
        layout_botones_camara.addWidget(self.shutdown_btn)
        layout_botones_camara.addWidget(self.combo_cameras)
        layout_botones_camara.addStretch()

        layout_overlay.addLayout(layout_botones_camara)
        layout_overlay.addStretch()
        
        self.splitter.addWidget(self.video_label)
        self.splitter.setSizes([640, 640])

    def update_frame(self, frame_bgr, frame_rgb, textos):
        if frame_rgb is not None:
            self.frame_actual_bgr = frame_bgr
            self.actual_qr_texts = textos
            
            alto, ancho, canales = frame_rgb.shape
            bytes_por_linea = canales * ancho
            img_qt = QImage(frame_rgb.data, ancho, alto, bytes_por_linea, QImage.Format.Format_RGB888)
            
            pixmap = QPixmap.fromImage(img_qt)
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.width(), self.video_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))

    def _procesar_clic_simple(self, text):
        self.clicks = 0
        self.last_key = None
        # AQUÍ LA VISTA DELEGA EN EL CONTROLADOR LA PETICIÓN DE LECTURA DE INTERFAZ
        self.ctrl.audio_service.read_text(text)
    
    def _procesar_doble_clic(self, func):
        func()

    def process_chortcut(self, tecla_id, text, func):
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
            self.click_timer.timeout.connect(lambda: self._procesar_clic_simple(text))
            self.click_timer.start(400)
        elif self.clicks == 2:
            if self.click_timer is not None and self.click_timer.isActive(): 
                self.click_timer.stop()
            self._procesar_doble_clic(func)
            self.clicks = 0
            self.last_key = None

    def update_icons(self, highcontrast_mode):
        self.highcontrast_mode = highcontrast_mode
        if highcontrast_mode:
            ruta_editar = os.path.join(self.icons_dir, "edit_cont.png")
            ruta_rotar = os.path.join(self.icons_dir, "sync_cont.png")
            ruta_apagar = os.path.join(self.icons_dir, "on-off-button_cont.png")
        else:
            ruta_editar = os.path.join(self.icons_dir, "edit.png")
            ruta_rotar = os.path.join(self.icons_dir, "sync.png")
            ruta_apagar = os.path.join(self.icons_dir, "on-off-button.png")
            
        self.edit_btn.setIcon(QIcon(ruta_editar))
        self.rotate_btn.setIcon(QIcon(ruta_rotar))
        self.shutdown_btn.setIcon(QIcon(ruta_apagar))

    # --- ACCIONES PURIFICADAS QUE SOLO DELEGAN ---
    def action_capture(self):
        if self.frame_actual_bgr is None: return
        self.ctrl.process_whole_frame(self.frame_actual_bgr, self.img_dir, self.read_generated_code)

    def action_var_review(self):
        self.ctrl.var_review(self.read_generated_code)

    def action_send(self):
        self.ctrl.send_to_microbit()

    def action_ia_explain(self):
        def actualizar_estado(texto, color_hex=None):
            self.status_label.setText(texto)
        self.ctrl.ia_explain_code(actualizar_estado)

    def action_change_tts(self):
        self.idx_tts, texto_boton = self.ctrl.change_tts(self.modos_tts, self.idx_tts)
        self.btn_tts.setText(texto_boton)

    def action_read_qrs(self):
        self.ctrl.read_qrs(self.frame_actual_bgr)

    def read_generated_code(self):
        self.caja_texto.clear()
        codigo_mostrar, estado, self.pitches_block, hay_error = self.ctrl.get_view_code()
        self.caja_texto.setPlainText(codigo_mostrar)
        self.status_label.setText(estado)
        
        if hay_error:
            self.ctrl.audio_service.read_text("Atención. Hay un error de sintaxis en el archivo.")

    def action_edit_code(self):
        if not self.edit_mode:
            self.edit_mode = True
            if self.highcontrast_mode:
                self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "diskette_cont.png")))
            else:
                self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "diskette.png")))
            self.caja_texto.setReadOnly(False)
            self.status_label.setText("Estado: MODO EDICIÓN ACTIVO")
        else:
            nuevo_codigo = self.caja_texto.toPlainText()
            exito, error = self.ctrl.save_manual_code(nuevo_codigo, self.pitches_block)
            
            if exito:
                self.edit_mode = False
                if self.highcontrast_mode:
                    self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "edit_cont.png")))
                else:
                    self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
                self.caja_texto.setReadOnly(True)
                self.read_generated_code()
            else:
                self.status_label.setText(f"Error al guardar: {error}")

    def action_save_shortcut(self):
        if self.edit_mode:
            nuevo_codigo = self.caja_texto.toPlainText()
            exito, _ = self.ctrl.save_manual_code(nuevo_codigo, self.pitches_block)
            if exito:
                self.edit_mode = False
                self.edit_btn.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
                self.caja_texto.setReadOnly(True)
                self.read_generated_code()
                self.status_label.setText("Estado: Guardado rápido completado")

    # --- CONTROL DE HARDWARE (MANTENIDO EN LA VISTA SOLO COMO BOTONES) ---
    def accion_rotar_camara(self):
        self.rotate_camera = not self.rotate_camera
        self.ctrl.set_rotation_camera(self.rotate_camera)

    def accion_apagar_camara(self):
        self.shutdown_camera = not self.shutdown_camera
        if self.shutdown_camera:
            self.ctrl.pause_camera_hardware()
            
            # Limpiamos la imagen y ponemos el fondo completamente negro
            self.video_label.clear()
            self.video_label.setStyleSheet("background-color: black;")
            
            self.status_label.setText("Estado: Cámara Apagada")
        else:
            # Quitamos el fondo negro al encender
            self.video_label.setStyleSheet("")
            idx = self.combo_cameras.currentData()
            self.ctrl.start_camera_hardware(idx, self.rotate_camera)
            self.status_label.setText("Estado: Cámara Activa")

    def accion_cambiar_camara(self, index):
        if not self.shutdown_camera:
            self.ctrl.pause_camera_hardware()
            self.video_label.clear() 
            id_real = self.combo_cameras.itemData(index)
            self.ctrl.start_camera_hardware(id_real, self.rotate_camera)

    def cleanup(self):
        self.ctrl.free_camera_resources()

    def pause_camera(self):
        self.ctrl.pause_camera_hardware()
        self.video_label.clear()
        self.video_label.setStyleSheet("background-color: black;")

    def resume_camera(self):
        if not self.shutdown_camera:
            # Nos aseguramos de limpiar el fondo negro al reanudar
            self.video_label.setStyleSheet("")
            idx = self.combo_cameras.currentData()
            self.ctrl.start_camera_hardware(idx, self.rotate_camera)