import os
import re
import threading
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QFrame, QSplitter)
from PyQt6.QtGui import QImage, QPixmap, QKeyEvent, QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtCore import Qt, QTimer, QRegularExpression
from core.audio import GestorVoz

# =========================================================
# HIGHLIGHTER PERSONALIZADO PARA SINTAXIS PYTHON (VS CODE LOOK)
# =========================================================
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reglas_estilo = []

        # Palabras clave de control de flujo
        formato_flow = QTextCharFormat()
        formato_flow.setForeground(QColor("#C586C0"))
        palabras_flow = [r'\bif\b', r'\belif\b', r'\belse\b', r'\bwhile\b', 
                         r'\bfor\b', r'\bin\b', r'\bbreak\b', r'\bcontinue\b', r'\breturn\b']
        for p in palabras_flow:
            self.reglas_estilo.append((QRegularExpression(p), formato_flow))

        # Estructuras de declaración
        formato_kw = QTextCharFormat()
        formato_kw.setForeground(QColor("#569CD6"))
        palabras_kw = [r'\bfrom\b', r'\bimport\b', r'\bdef\b', r'\bclass\b', r'\bpass\b', r'\bglobal\b', r'\bas\b']
        for p in palabras_kw:
            self.reglas_estilo.append((QRegularExpression(p), formato_kw))

        # Booleanos y vacíos
        formato_bool = QTextCharFormat()
        formato_bool.setForeground(QColor("#569CD6"))
        for p in [r'\bTrue\b', r'\bFalse\b', r'\bNone\b']:
            self.reglas_estilo.append((QRegularExpression(p), formato_bool))

        # Funciones invocadas
        formato_func = QTextCharFormat()
        formato_func.setForeground(QColor("#DCDCAA"))
        self.reglas_estilo.append((QRegularExpression(r'\b[a-zA-Z_]\w*(?=\()'), formato_func))

        # Números literales
        formato_num = QTextCharFormat()
        formato_num.setForeground(QColor("#B5CEA8"))
        self.reglas_estilo.append((QRegularExpression(r'\b\d+\.?\d*\b'), formato_num))

        # Cadenas de texto (Strings)
        formato_str = QTextCharFormat()
        formato_str.setForeground(QColor("#CE9178"))
        self.reglas_estilo.append((QRegularExpression(r'".*?"'), formato_str))
        self.reglas_estilo.append((QRegularExpression(r"'.*?'"), formato_str))

        # Comentarios
        formato_comment = QTextCharFormat()
        formato_comment.setForeground(QColor("#6A9955"))
        self.reglas_estilo.append((QRegularExpression(r'#.*'), formato_comment))

    def highlightBlock(self, text):
        for expresion, formato in self.reglas_estilo:
            match_iterator = expresion.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), formato)

# =========================================================
# COMPONENTE DE LA PESTAÑA DE LA CÁMARA
# =========================================================
class TabCamara(QWidget):
    def __init__(self, workspace_dir, vision_engine, traductor, ai_manager):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.ruta_img = os.path.join(self.workspace_dir, "inputs", "program.jpg")
        self.ruta_codigo = os.path.join(self.workspace_dir, "outputs", "MicroBit_Code.py")
        
        # Motores inyectados
        self.vision = vision_engine
        self.traductor = traductor
        self.ai_manager = ai_manager

        # Estados de control accesibles
        self.modo_edicion = False
        self.clics = 0
        self.timer_clic = None
        self.ultima_tecla = None
        self.textos_qr_actuales = []
        self.bloque_pitches = []

        self._setup_ui()
        
        # Bucle asíncrono para captura de fotogramas (Webcam)
        self.timer_camara = QTimer()
        self.timer_camara.timeout.connect(self.actualizar_frame)
        self.timer_camara.start(15) # ~60 FPS nativos de refresco de buffer

        self.leer_codigo_generado()

    def _setup_ui(self):
        layout_principal = QHBoxLayout(self)
        
        # Splitter para poder redimensionar de forma elástica el editor y la cámara
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_principal.addWidget(self.splitter)

        # -------------------------------------------------
        # PANEL IZQUIERDO: CONTROLES Y EDITOR DE CÓDIGO
        # -------------------------------------------------
        panel_izquierdo = QFrame()
        layout_izq = QVBoxLayout(panel_izquierdo)
        
        lbl_ctrl = QLabel("CONTROLES")
        lbl_ctrl.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        lbl_ctrl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_izq.addWidget(lbl_ctrl)

        # Barra horizontal de botones táctiles/atendidos
        layout_botones = QHBoxLayout()
        
        self.btn_capturar = QPushButton("Tomar Foto")
        self.btn_capturar.setStyleSheet("background-color: #0052cc; color: white; font-weight: bold; padding: 10px;")
        self.btn_capturar.clicked.connect(self.accion_capturar)
        layout_botones.addWidget(self.btn_capturar)

        self.btn_enviar = QPushButton("Enviar a MicroBit")
        self.btn_enviar.setStyleSheet("background-color: #2FA572; color: white; font-weight: bold; padding: 10px;")
        self.btn_enviar.clicked.connect(self.accion_enviar)
        layout_botones.addWidget(self.btn_enviar)

        self.btn_ia = QPushButton("Explicar con IA")
        self.btn_ia.setStyleSheet("background-color: #8E44AD; color: white; font-weight: bold; padding: 10px;")
        self.btn_ia.clicked.connect(self.accion_explicar_ia)
        layout_botones.addWidget(self.btn_ia)

        self.btn_leer_qrs = QPushButton("Leer QRs Mesa")
        self.btn_leer_qrs.setStyleSheet("background-color: #4A235A; color: white; font-weight: bold; padding: 10px;")
        self.btn_leer_qrs.clicked.connect(self.accion_leer_qrs_pantalla)
        layout_botones.addWidget(self.btn_leer_qrs)

        self.btn_editar = QPushButton("Editar Código")
        self.btn_editar.setStyleSheet("background-color: #D4AC0D; color: white; font-weight: bold; padding: 10px;")
        self.btn_editar.clicked.connect(self.accion_editar_codigo)
        layout_botones.addWidget(self.btn_editar)

        layout_izq.addLayout(layout_botones)

        # Monitor/Editor de texto central (Dark Theme)
        self.caja_texto = QTextEdit()
        self.caja_texto.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4; font-family: 'Consolas', monospace; font-size: 14px; padding: 10px;")
        self.caja_texto.setReadOnly(True)
        
        # Enlazamos el formateador de sintaxis al documento de texto
        self.highlighter = PythonHighlighter(self.caja_texto.document())
        layout_izq.addWidget(self.caja_texto)

        self.status_label = QLabel("Estado: Cámara Activa")
        self.status_label.setStyleSheet("color: gray; font-size: 12px;")
        layout_izq.addWidget(self.status_label)

        self.splitter.addWidget(panel_izquierdo)

        # -------------------------------------------------
        # PANEL DERECHO: VISOR DE VIDEO DE ALTA VELOCIDAD
        # -------------------------------------------------
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000000; border-radius: 4px;")
        
        # --- AÑADE ESTAS TRES LÍNEAS AQUÍ ---
        # Ignoramos la política de tamaño para que el QPixmap no redimensione la ventana
        from PyQt6.QtWidgets import QSizePolicy
        self.video_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_label.setMinimumSize(400, 300) # Un tamaño base por seguridad
        
        self.splitter.addWidget(self.video_label)

        # Proporciones iniciales del divisor (50% - 50%)
        self.splitter.setSizes([640, 640])

    # =========================================================
    # ACTUALIZACIÓN DE FRAME (OPENCV -> PYQT)
    # =========================================================
    def actualizar_frame(self):
        frame_bgr, frame_rgb, textos = self.vision.markElems()
        
        if frame_rgb is not None:
            self.frame_actual_bgr = frame_bgr
            self.textos_qr_actuales = textos
            
            # Conversión óptima del array de Numpy a QImage de Qt
            alto, ancho, canales = frame_rgb.shape
            bytes_por_linea = canales * ancho
            img_qt = QImage(frame_rgb.data, ancho, alto, bytes_por_linea, QImage.Format.Format_RGB888)
            
            # Ajustamos la escala manteniendo la relación de aspecto del stream original
            pixmap = QPixmap.fromImage(img_qt)
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.width(), self.video_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))

    # =========================================================
    # FILTRO ACCESIBLE DE TECLADO MÁSTER (SINGLE / DOUBLE CLICK)
    # =========================================================
    def _procesar_clic_simple(self, text):
        self.clics = 0
        self.ultima_tecla = None
        GestorVoz.leer_texto(text)

    def _procesar_doble_clic(self, func):
        func()
    
    def _tecla_pulsada(self, tecla_id, text, func):
        if self.modo_edicion:
            return 
            
        if self.ultima_tecla != tecla_id:
            if self.timer_clic and self.timer_clic.isActive():
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
            if self.timer_clic and self.timer_clic.isActive():
                self.timer_clic.stop()
            self._procesar_doble_clic(func)
            self.clics = 0
            self.ultima_tecla = None

    # =========================================================
    # PROCESAMIENTOS DE NEGOCIO (DELEGADOS)
    # =========================================================
    def accion_capturar(self):
        if hasattr(self, 'frame_actual_bgr'):
            self.vision.takePhoto(self.frame_actual_bgr, self.ruta_img)
            matriz_espacial = self.vision.get_command_matrix()
            self.traductor.generar_codigo(matriz_espacial, self.ruta_codigo) 
            self.leer_codigo_generado()

    def accion_enviar(self):
        self.traductor.subir(self.ruta_codigo)

    def accion_leer_qrs_pantalla(self):
        GestorVoz.leer_qrs_pantalla(self.textos_qr_actuales)

    def accion_explicar_ia(self):
        def actualizar_estado(texto, color_hex):
            self.status_label.setText(texto)
            self.status_label.setStyleSheet(f"color: {color_hex};")
            
        threading.Thread(target=lambda: self.ai_manager.explicar_codigo(self.ruta_codigo, actualizar_estado), daemon=True).start()

    # =========================================================
    # RENDERIZADO Y TRATAMIENTO TEXTUAL
    # =========================================================
    def leer_codigo_generado(self):
        self.caja_texto.clear()
        try:
            with open(self.ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
            
            lineas = codigo.split('\n')
            idx_ultimo_pitch = -1
            for i, linea in enumerate(lineas):
                if "music.pitch" in linea: idx_ultimo_pitch = i
                if linea.startswith("while ") or linea.startswith("if ") or linea.startswith("def "): break

            if idx_ultimo_pitch != -1:
                lineas_visibles = []
                self.bloque_pitches = [] 
                for i, linea in enumerate(lineas):
                    if i <= idx_ultimo_pitch:
                        if linea.startswith("import ") or linea.startswith("from "): lineas_visibles.append(linea)
                        elif "music.pitch" in linea: self.bloque_pitches.append(linea)
                    else:
                        if i == idx_ultimo_pitch + 1 and linea.strip() == "" and lineas_visibles and lineas_visibles[-1].strip() == "": continue
                        lineas_visibles.append(linea)
                codigo_mostrar = "\n".join(lineas_visibles)
            else:
                self.bloque_pitches = []
                codigo_mostrar = codigo

            self.caja_texto.setPlainText(codigo_mostrar)

            try:
                compile(codigo_mostrar, '<string>', 'exec')
                self.status_label.setText("Estado: Código sin errores")
                self.status_label.setStyleSheet("color: #2FA572;")
            except SyntaxError as e:
                self.status_label.setText(f"Error de Sintaxis en línea {e.lineno}")
                self.status_label.setStyleSheet("color: #FF4C4C;")
                GestorVoz.leer_texto("Atención. Hay un error de sintaxis en el archivo.")

        except FileNotFoundError:
            self.caja_texto.setPlainText("# Archivo no generado de momento.")
            self.status_label.setText("Estado: Esperando captura...")

    def _guardar_codigo_archivo(self):
        nuevo_codigo = self.caja_texto.toPlainText()
        if hasattr(self, 'bloque_pitches') and self.bloque_pitches:
            lineas_editadas = nuevo_codigo.split('\n')
            idx_insert = next((i + 1 for i, linea in enumerate(lineas_editadas) if not (linea.startswith("import ") or linea.startswith("from ") or linea.strip() == "")), 0)
            
            if idx_insert < len(lineas_editadas) and lineas_editadas[idx_insert].strip() != "":
                lineas_finales = lineas_editadas[:idx_insert] + self.bloque_pitches + [""] + lineas_editadas[idx_insert:]
            else:
                lineas_finales = lineas_editadas[:idx_insert] + self.bloque_pitches + lineas_editadas[idx_insert:]
            codigo_a_guardar = "\n".join(lineas_finales)
        else:
            codigo_a_guardar = nuevo_codigo
            
        try:
            with open(self.ruta_codigo, "w", encoding="utf-8") as f:
                f.write(codigo_a_guardar)
            return True
        except Exception as e:
            self.status_label.setText(f"Error al guardar: {e}")
            self.status_label.setStyleSheet("color: #FF4C4C;")
            return False

    def accion_editar_codigo(self):
        if not self.modo_edicion:
            self.modo_edicion = True
            self.btn_editar.setText("Guardar Código")
            self.btn_editar.setStyleSheet("background-color: #E74C3C; color: white; font-weight: bold; padding: 10px;")
            self.caja_texto.setReadOnly(False)
            self.status_label.setText("Estado: MODO EDICIÓN ACTIVO")
            self.status_label.setStyleSheet("color: #D4AC0D;")
        else:
            if self._guardar_codigo_archivo():
                self.modo_edicion = False
                self.btn_editar.setText("Editar Código")
                self.btn_editar.setStyleSheet("background-color: #D4AC0D; color: white; font-weight: bold; padding: 10px;")
                self.leer_codigo_generado()

    def accion_atajo_guardar(self):
        if self.modo_edicion and self._guardar_codigo_archivo():
            self.leer_codigo_generado()
            self.caja_texto.setReadOnly(False)
            self.status_label.setText("Estado: Guardado rápido completado")
            self.status_label.setStyleSheet("color: #569CD6;")

    def cleanup(self):
        """Libera la cámara al cerrar el widget de forma segura."""
        self.timer_camara.stop()
        self.vision.free()