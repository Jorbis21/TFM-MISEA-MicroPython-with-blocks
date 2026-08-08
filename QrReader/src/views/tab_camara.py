import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QFrame, QSplitter, QComboBox, QSizePolicy)
from PyQt6.QtGui import (QImage, QPixmap, QIcon)
from PyQt6.QtCore import Qt, QTimer, QSize
from views.highlighter import PythonHighlighter
from utils.constants import TTSMode
from controllers.camera_worker import CameraWorker

class TabCamara(QWidget):
    def __init__(self, workspace_dir, assets_dir, camera_ctrl):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.icons_dir = os.path.join(assets_dir, "icons")
        self.ruta_img = os.path.join(self.workspace_dir, "inputs", "program.jpg")
        
        self.controlador = camera_ctrl

        self.modo_edicion = False
        self.rotar_camara = False
        self.apagar_camara = False
        self.modo_alto_contraste = True
        self.clics = 0
        self.ultima_tecla = None
        self.timer_clic = None
        
        self.textos_qr_actuales = []
        self.bloque_pitches = []
        self.frame_actual_bgr = None

        
        self.controlador.camera_thr.nuevo_frame.connect(self.actualizar_frame)

        self._setup_ui()
        self.leer_codigo_generado()
        self.reanudar_camara()

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
        
        self.btn_editar = QPushButton()
        self.btn_editar.setObjectName("btn_editar")
        self.btn_editar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ruta_icono_editar = os.path.join(self.icons_dir, "edit_cont.png")
        self.btn_editar.setIcon(QIcon(ruta_icono_editar))
        self.btn_editar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_editar.clicked.connect(self.accion_editar_codigo)
        
        layout_h_texto.addWidget(self.btn_editar)
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

        self.btn_rotar = QPushButton()
        self.btn_rotar.setObjectName("btn_overlay")
        self.btn_apagar = QPushButton()
        self.btn_apagar.setObjectName("btn_overlay")

        self.btn_rotar.setIcon(QIcon(os.path.join(self.icons_dir, "sync_cont.png")))
        self.btn_apagar.setIcon(QIcon(os.path.join(self.icons_dir, "on-off-button_cont.png")))

        tamano_icono = QSize(24, 24)
        self.btn_rotar.setIconSize(tamano_icono)
        self.btn_apagar.setIconSize(tamano_icono)

        self.btn_apagar.clicked.connect(self.accion_apagar_camara)
        self.btn_rotar.clicked.connect(self.accion_rotar_camara)

        self.combo_camaras = QComboBox()
        self.combo_camaras.setObjectName("combo_camaras")
        self.combo_camaras.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        camaras_reales = CameraWorker.detectar_camaras() 
        for cam_id in camaras_reales:
            nombre = "Cámara Principal" if cam_id == 0 else f"Cámara Secundaria ({cam_id})"
            self.combo_camaras.addItem(nombre, userData=cam_id)
            
        if len(camaras_reales) <= 1:
            self.combo_camaras.hide()
            
        self.combo_camaras.currentIndexChanged.connect(self.accion_cambiar_camara)

        layout_botones_camara.addWidget(self.btn_rotar)
        layout_botones_camara.addWidget(self.btn_apagar)
        layout_botones_camara.addWidget(self.combo_camaras)
        layout_botones_camara.addStretch()

        layout_overlay.addLayout(layout_botones_camara)
        layout_overlay.addStretch()
        
        self.splitter.addWidget(self.video_label)
        self.splitter.setSizes([640, 640])

    def actualizar_frame(self, frame_bgr, frame_rgb, textos):
        if frame_rgb is not None:
            self.frame_actual_bgr = frame_bgr
            self.textos_qr_actuales = textos
            
            alto, ancho, canales = frame_rgb.shape
            bytes_por_linea = canales * ancho
            img_qt = QImage(frame_rgb.data, ancho, alto, bytes_por_linea, QImage.Format.Format_RGB888)
            
            pixmap = QPixmap.fromImage(img_qt)
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.width(), self.video_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))

    def _procesar_clic_simple(self, text):
        self.clics = 0
        self.ultima_tecla = None
        # AQUÍ LA VISTA DELEGA EN EL CONTROLADOR LA PETICIÓN DE LECTURA DE INTERFAZ
        self.controlador.audio_service.read_text(text)
    
    def _procesar_doble_clic(self, func):
        func()

    def procesar_atajo_teclado(self, tecla_id, text, func):
        if self.modo_edicion: return 
        if self.ultima_tecla != tecla_id:
            if self.timer_clic is not None and self.timer_clic.isActive(): 
                self.timer_clic.stop()
            self.clics = 0
            self.ultima_tecla = tecla_id
            
        self.clics += 1
        if self.clics == 1:
            self.timer_clic = QTimer()
            self.timer_clic.setSingleShot(True)
            self.timer_clic.timeout.connect(lambda: self._procesar_clic_simple(text))
            self.timer_clic.start(400)
        elif self.clics == 2:
            if self.timer_clic is not None and self.timer_clic.isActive(): 
                self.timer_clic.stop()
            self._procesar_doble_clic(func)
            self.clics = 0
            self.ultima_tecla = None

    def actualizar_iconos(self, modo_alto_contraste):
        self.modo_alto_contraste = modo_alto_contraste
        if modo_alto_contraste:
            ruta_editar = os.path.join(self.icons_dir, "edit_cont.png")
            ruta_rotar = os.path.join(self.icons_dir, "sync_cont.png")
            ruta_apagar = os.path.join(self.icons_dir, "on-off-button_cont.png")
        else:
            ruta_editar = os.path.join(self.icons_dir, "edit.png")
            ruta_rotar = os.path.join(self.icons_dir, "sync.png")
            ruta_apagar = os.path.join(self.icons_dir, "on-off-button.png")
            
        self.btn_editar.setIcon(QIcon(ruta_editar))
        self.btn_rotar.setIcon(QIcon(ruta_rotar))
        self.btn_apagar.setIcon(QIcon(ruta_apagar))

    # --- ACCIONES PURIFICADAS QUE SOLO DELEGAN ---
    def action_capture(self):
        if self.frame_actual_bgr is None: return
        self.controlador.process_whole_frame(self.frame_actual_bgr, self.ruta_img, self.leer_codigo_generado)

    def action_var_review(self):
        self.controlador.var_review(self.leer_codigo_generado)

    def action_send(self):
        self.controlador.send_to_microbit()

    def action_ia_explain(self):
        def actualizar_estado(texto, color_hex=None):
            self.status_label.setText(texto)
        self.controlador.ia_explain_code(actualizar_estado)

    def action_change_tts(self):
        self.idx_tts, texto_boton = self.controlador.change_tts(self.modos_tts, self.idx_tts)
        self.btn_tts.setText(texto_boton)

    def action_read_qrs(self):
        self.controlador.read_qrs(self.frame_actual_bgr)

    def leer_codigo_generado(self):
        self.caja_texto.clear()
        codigo_mostrar, estado, self.bloque_pitches, hay_error = self.controlador.get_view_code()
        self.caja_texto.setPlainText(codigo_mostrar)
        self.status_label.setText(estado)
        
        if hay_error:
            self.controlador.audio_service.read_text("Atención. Hay un error de sintaxis en el archivo.")

    def accion_editar_codigo(self):
        if not self.modo_edicion:
            self.modo_edicion = True
            if self.modo_alto_contraste:
                self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "diskette_cont.png")))
            else:
                self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "diskette.png")))
            self.caja_texto.setReadOnly(False)
            self.status_label.setText("Estado: MODO EDICIÓN ACTIVO")
        else:
            nuevo_codigo = self.caja_texto.toPlainText()
            exito, error = self.controlador.save_manual_code(nuevo_codigo, self.bloque_pitches)
            
            if exito:
                self.modo_edicion = False
                if self.modo_alto_contraste:
                    self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "edit_cont.png")))
                else:
                    self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
                self.caja_texto.setReadOnly(True)
                self.leer_codigo_generado()
            else:
                self.status_label.setText(f"Error al guardar: {error}")

    def accion_atajo_guardar(self):
        if self.modo_edicion:
            nuevo_codigo = self.caja_texto.toPlainText()
            exito, _ = self.controlador.save_manual_code(nuevo_codigo, self.bloque_pitches)
            if exito:
                self.modo_edicion = False
                self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
                self.caja_texto.setReadOnly(True)
                self.leer_codigo_generado()
                self.status_label.setText("Estado: Guardado rápido completado")

    # --- CONTROL DE HARDWARE (MANTENIDO EN LA VISTA SOLO COMO BOTONES) ---
    def accion_rotar_camara(self):
        self.rotar_camara = not self.rotar_camara
        self.controlador.set_rotation_camera(self.rotar_camara)

    def accion_apagar_camara(self):
        self.apagar_camara = not self.apagar_camara
        if self.apagar_camara:
            self.controlador.pause_camera_hardware()
            
            # Limpiamos la imagen y ponemos el fondo completamente negro
            self.video_label.clear()
            self.video_label.setStyleSheet("background-color: black;")
            
            self.status_label.setText("Estado: Cámara Apagada")
        else:
            # Quitamos el fondo negro al encender
            self.video_label.setStyleSheet("")
            idx = self.combo_camaras.currentData()
            self.controlador.start_camera_hardware(idx, self.rotar_camara)
            self.status_label.setText("Estado: Cámara Activa")

    def accion_cambiar_camara(self, index):
        if not self.apagar_camara:
            self.controlador.pause_camera_hardware()
            self.video_label.clear() 
            id_real = self.combo_camaras.itemData(index)
            self.controlador.start_camera_hardware(id_real, self.rotar_camara)

    def cleanup(self):
        self.controlador.free_camera_resources()

    def pausar_camara(self):
        self.controlador.pause_camera_hardware()
        self.video_label.clear()
        self.video_label.setStyleSheet("background-color: black;")

    def reanudar_camara(self):
        if not self.apagar_camara:
            # Nos aseguramos de limpiar el fondo negro al reanudar
            self.video_label.setStyleSheet("")
            idx = self.combo_camaras.currentData()
            self.controlador.start_camera_hardware(idx, self.rotar_camara)