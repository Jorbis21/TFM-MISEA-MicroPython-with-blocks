import os
import re
import threading
import cv2  
import time 
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QFrame, QSplitter, QComboBox, QSizePolicy)
from PyQt6.QtGui import (QImage, QPixmap, QKeyEvent, QTextCharFormat, QColor, 
                         QSyntaxHighlighter, QIcon)
# --- AÑADIDOS: QThread y pyqtSignal para el multihilo ---
from PyQt6.QtCore import Qt, QTimer, QRegularExpression, QSize, QThread, pyqtSignal
from core.audio import GestorVoz

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reglas_estilo = []

        formato_error = QTextCharFormat()
        formato_error.setForeground(QColor("#F44747")) 
        formato_error.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        formato_error.setUnderlineColor(QColor("#F44747"))
        self.reglas_estilo.append((QRegularExpression(r'# ERROR.*'), formato_error))

        formato_flow = QTextCharFormat()
        formato_flow.setForeground(QColor("#C586C0"))
        palabras_flow = [r'\bif\b', r'\belif\b', r'\belse\b', r'\bwhile\b', 
                         r'\bfor\b', r'\bin\b', r'\bbreak\b', r'\bcontinue\b', r'\breturn\b']
        for p in palabras_flow:
            self.reglas_estilo.append((QRegularExpression(p), formato_flow))

        formato_kw = QTextCharFormat()
        formato_kw.setForeground(QColor("#569CD6"))
        palabras_kw = [r'\bfrom\b', r'\bimport\b', r'\bdef\b', r'\bclass\b', r'\bpass\b', r'\bglobal\b', r'\bas\b']
        for p in palabras_kw:
            self.reglas_estilo.append((QRegularExpression(p), formato_kw))

        formato_bool = QTextCharFormat()
        formato_bool.setForeground(QColor("#569CD6"))
        for p in [r'\bTrue\b', r'\bFalse\b', r'\bNone\b']:
            self.reglas_estilo.append((QRegularExpression(p), formato_bool))

        formato_func = QTextCharFormat()
        formato_func.setForeground(QColor("#DCDCAA"))
        self.reglas_estilo.append((QRegularExpression(r'\b[a-zA-Z_]\w*(?=\()'), formato_func))

        formato_num = QTextCharFormat()
        formato_num.setForeground(QColor("#B5CEA8"))
        self.reglas_estilo.append((QRegularExpression(r'\b\d+\.?\d*\b'), formato_num))

        formato_str = QTextCharFormat()
        formato_str.setForeground(QColor("#CE9178"))
        self.reglas_estilo.append((QRegularExpression(r'".*?"'), formato_str))
        self.reglas_estilo.append((QRegularExpression(r"'.*?'"), formato_str))

        formato_comment = QTextCharFormat()
        formato_comment.setForeground(QColor("#6A9955"))
        self.reglas_estilo.append((QRegularExpression(r'#.*'), formato_comment))

    def highlightBlock(self, text):
        for expresion, formato in self.reglas_estilo:
            match_iterator = expresion.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), formato)


# --- NUEVA CLASE: Hilo independiente para la cámara ---
class HiloCamara(QThread):
    # Definimos la señal que enviará los datos al hilo principal (GUI) de forma segura
    nuevo_frame = pyqtSignal(object, object, list) 

    def __init__(self, vision_engine, parent=None):
        super().__init__(parent)
        self.vision = vision_engine
        self.corriendo = True
        self.rotar = False

    def run(self):
        while self.corriendo:
            # Todo el procesamiento pesado de OpenCV ocurre aquí, sin bloquear la GUI
            frame_bgr, frame_rgb, textos = self.vision.markElems(self.rotar)
            if frame_rgb is not None:
                self.nuevo_frame.emit(frame_bgr, frame_rgb, textos)
            time.sleep(0.015) 

    def stop(self):
        self.corriendo = False
        self.wait()


class TabCamara(QWidget):
    def __init__(self, workspace_dir, assets_dir, vision_engine, traductor, ai_manager):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.icons_dir = os.path.join(assets_dir, "icons")
        self.ruta_img = os.path.join(self.workspace_dir, "inputs", "program.jpg")
        self.ruta_codigo = os.path.join(self.workspace_dir, "outputs", "MicroBit_Code.py")
        self.ruta_estado = os.path.join(self.workspace_dir, "outputs", "program_state.json")
        
        self.vision = vision_engine
        self.traductor = traductor
        self.ai_manager = ai_manager

        self.modo_edicion = False
        self.rotar_camara = False
        self.apagar_camara = False
        self.modo_alto_contraste = True
        self.clics = 0
        self.timer_clic = None
        self.ultima_tecla = None
        self.textos_qr_actuales = []
        self.bloque_pitches = []

        self.estoy_ampliando = False
        self.super_matriz = []
        self.cola_ampliaciones = []

        self._cargar_estado()

        self._setup_ui()
        
        # --- SUSTITUCIÓN DEL QTIMER POR EL QTHREAD ---
        self.hilo_camara = HiloCamara(self.vision)
        self.hilo_camara.nuevo_frame.connect(self.actualizar_frame)

        self.leer_codigo_generado()
        self.reanudar_camara()

    def _guardar_estado(self):
        try:
            estado = {
                "matriz": self.super_matriz,
                "historial": getattr(self.traductor, 'historial_interacciones', [])
            }
            with open(self.ruta_estado, "w", encoding="utf-8") as f:
                json.dump(estado, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error guardando estado: {e}")

    def _cargar_estado(self):
        if os.path.exists(self.ruta_estado):
            try:
                with open(self.ruta_estado, "r", encoding="utf-8") as f:
                    estado = json.load(f)
                    self.super_matriz = estado.get("matriz", [])
                    if hasattr(self.traductor, 'historial_interacciones'):
                        self.traductor.historial_interacciones = estado.get("historial", [])
            except Exception as e:
                print(f"Error cargando estado: {e}")

    def _detectar_camaras(self):
        camaras_activas = []
        for i in range(3):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
            if cap is not None and cap.isOpened():
                camaras_activas.append(i)
                cap.release()
        if not camaras_activas:
            camaras_activas = [0]
        return camaras_activas

    def _setup_ui(self):
        layout_principal = QHBoxLayout(self)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_principal.addWidget(self.splitter)

        panel_izquierdo = QFrame()
        layout_izq = QVBoxLayout(panel_izquierdo)

        layout_botones = QHBoxLayout()
        
        self.btn_capturar = QPushButton("Tomar Foto")
        self.btn_capturar.setObjectName("btn_capturar")
        self.btn_capturar.clicked.connect(self.accion_capturar)
        layout_botones.addWidget(self.btn_capturar)
        
        self.btn_enviar = QPushButton("Enviar a MicroBit")
        self.btn_enviar.setObjectName("btn_enviar")
        self.btn_enviar.clicked.connect(self.accion_enviar)
        layout_botones.addWidget(self.btn_enviar)

        self.btn_ia = QPushButton("Explicar con IA")
        self.btn_ia.setObjectName("btn_ia")
        self.btn_ia.clicked.connect(self.accion_explicar_ia)
        layout_botones.addWidget(self.btn_ia)

        self.btn_leer = QPushButton("Leer QRs")
        self.btn_leer.setObjectName("btn_leer")
        self.btn_leer.clicked.connect(self.accion_leer_qrs_pantalla)
        layout_botones.addWidget(self.btn_leer)

        self.modos_tts = [
            {"texto": "Voz: PC", "valor": "pc"},
            {"texto": "Voz: Placa", "valor": "placa"},
            {"texto": "Voz: Apagada", "valor": "apagado"}
        ]
        self.idx_tts = 0

        self.btn_tts = QPushButton(self.modos_tts[self.idx_tts]["texto"])
        self.btn_tts.setObjectName("btn_tts")
        self.btn_tts.clicked.connect(self.accion_cambiar_tts)
        layout_botones.addWidget(self.btn_tts)

        self.btn_repaso = QPushButton("Modificar Variables")
        self.btn_repaso.setObjectName("btn_repaso")
        self.btn_repaso.clicked.connect(self.accion_repasar_variables)
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
        camaras_reales = self._detectar_camaras()
        
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

    def _fusionar_matrices(self, matriz_base, matriz_nueva, nexos_esperados, direccion="desconocida"):
        genericos = ["valor_variable", "numero", "texto", "verdadero", "falso", "imagen"]
        nexos_fuertes = [n for n in nexos_esperados if str(n).strip().lower() not in genericos]
        anclajes = nexos_fuertes if nexos_fuertes else nexos_esperados
        
        nueva_super_matriz = [fila.copy() for fila in matriz_base]
        
        if direccion == "lateral":
            filas_mapeadas_en_nueva = set()
            offset_c_global = 0 
            
            for nexo in anclajes:
                nexo_str = str(nexo).strip().lower()
                r_base, c_base, r_nueva, c_nueva = -1, -1, -1, -1
                
                for r in range(len(nueva_super_matriz)):
                    for c in range(len(nueva_super_matriz[r])):
                        if str(nueva_super_matriz[r][c]).strip().lower() == nexo_str:
                            r_base, c_base = r, c
                            break
                    if r_base != -1: break
                
                for r in range(len(matriz_nueva)):
                    for c in range(len(matriz_nueva[r])):
                        if str(matriz_nueva[r][c]).strip().lower() == nexo_str:
                            r_nueva, c_nueva = r, c
                            break
                    if r_nueva != -1: break
                
                if r_base != -1 and r_nueva != -1:
                    filas_mapeadas_en_nueva.add(r_nueva)
                    offset_c_global = c_base - c_nueva
                    
                    for c in range(c_nueva + 1, len(matriz_nueva[r_nueva])):
                        val = matriz_nueva[r_nueva][c]
                        target_c = c + offset_c_global
                        while len(nueva_super_matriz[r_base]) <= target_c:
                            nueva_super_matriz[r_base].append("")
                        if val != "":
                            nueva_super_matriz[r_base][target_c] = val
                            
            if filas_mapeadas_en_nueva:
                max_r_mapeada = max(filas_mapeadas_en_nueva)
                for r in range(max_r_mapeada + 1, len(matriz_nueva)):
                    nueva_fila = []
                    for c in range(len(matriz_nueva[r])):
                        val = matriz_nueva[r][c]
                        target_c = c + offset_c_global
                        if target_c >= 0:
                            while len(nueva_fila) <= target_c:
                                nueva_fila.append("")
                            if val != "":
                                nueva_fila[target_c] = val
                    nueva_super_matriz.append(nueva_fila)
            else:
                for r in range(len(matriz_nueva)):
                    nueva_super_matriz.append(matriz_nueva[r])
                    
        elif direccion == "inferior":
            ancla_base_r, c_base = -1, -1
            ancla_nueva_r, c_nueva = -1, -1
            nexo_usado = None
            
            for nexo in anclajes:
                nexo_str = str(nexo).strip().lower()
                for r in range(len(nueva_super_matriz)-1, -1, -1):
                    for c in range(len(nueva_super_matriz[r])):
                        if str(nueva_super_matriz[r][c]).strip().lower() == nexo_str:
                            ancla_base_r, c_base = r, c
                            break
                    if ancla_base_r != -1: break
                
                for r in range(len(matriz_nueva)):
                    for c in range(len(matriz_nueva[r])):
                        if str(matriz_nueva[r][c]).strip().lower() == nexo_str:
                            ancla_nueva_r, c_nueva = r, c
                            break
                    if ancla_nueva_r != -1: break
                
                if ancla_base_r != -1 and ancla_nueva_r != -1:
                    nexo_usado = nexo
                    break
            
            if nexo_usado:
                offset_c = c_base - c_nueva
                
                for c in range(c_nueva + 1, len(matriz_nueva[ancla_nueva_r])):
                    val = matriz_nueva[ancla_nueva_r][c]
                    target_c = c + offset_c
                    while len(nueva_super_matriz[ancla_base_r]) <= target_c:
                        nueva_super_matriz[ancla_base_r].append("")
                    if val != "":
                        nueva_super_matriz[ancla_base_r][target_c] = val
                
                for r in range(ancla_nueva_r + 1, len(matriz_nueva)):
                    nueva_fila = []
                    for c in range(len(matriz_nueva[r])):
                        val = matriz_nueva[r][c]
                        target_c = c + offset_c
                        if target_c >= 0:
                            while len(nueva_fila) <= target_c:
                                nueva_fila.append("")
                            if val != "":
                                nueva_fila[target_c] = val
                    nueva_super_matriz.append(nueva_fila)
            else:
                for r in range(len(matriz_nueva)):
                    nueva_super_matriz.append(matriz_nueva[r])
        else:
            for r in range(len(matriz_nueva)):
                nueva_super_matriz.append(matriz_nueva[r])
                
        return nueva_super_matriz

    def accion_repasar_variables(self):
        if not self.super_matriz:
            GestorVoz.leer_texto_interrumpiendo("Primero debes capturar un programa para poder modificar sus variables.")
            return
            
        GestorVoz.leer_texto_interrumpiendo("Iniciando el modo de repaso de variables.")
        
        def logica_repaso():
            self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, modo_repaso=True)
            self._guardar_estado()
            QTimer.singleShot(0, self.leer_codigo_generado)
            
        threading.Thread(target=logica_repaso, daemon=True).start()

    def accion_capturar(self):
        GestorVoz.leer_texto("Capturando.")
        if not hasattr(self, 'frame_actual_bgr'): return
        
        self.vision.takePhoto(self.frame_actual_bgr, self.ruta_img)
        matriz_espacial = self.vision.get_command_matrix()
        
        if self.estoy_ampliando:
            self.super_matriz = self._fusionar_matrices(
                self.super_matriz, 
                matriz_espacial, 
                getattr(self, 'nexos_pendientes', []), 
                getattr(self, 'direccion_actual', "desconocida")
            )
        else:
            self.super_matriz = matriz_espacial
            self.cola_ampliaciones = [] 
            
        desbordamiento = self.vision.comprobar_desbordamiento()
        
        if desbordamiento:
            if desbordamiento.get("derecha"):
                self.cola_ampliaciones.append(("lateral", desbordamiento["derecha"]))
            
            if desbordamiento.get("abajo"):
                self.cola_ampliaciones.append(("inferior", [desbordamiento["abajo"]]))

        self._procesar_siguiente_ampliacion()

    def _procesar_siguiente_ampliacion(self):
        if not self.cola_ampliaciones:
            self.estoy_ampliando = False
            self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo) 
            self._guardar_estado()
            self.leer_codigo_generado()
            return

        direccion, nexos = self.cola_ampliaciones.pop(0)
        
        self.direccion_actual = direccion
        self.nexos_pendientes = nexos

        nombres_pronunciar = []
        for n in nexos:
            pronunciacion = self.traductor.tabla_simbolos.get(n.lower(), {}).get("pronunciacion", n)
            if pronunciacion not in nombres_pronunciar:
                nombres_pronunciar.append(pronunciacion)
                
        nombres_str = ", y ".join(nombres_pronunciar)
        
        def logica_voz_expansion():
            if self.traductor.voice_manager:
                respuesta = self.traductor.voice_manager.bucle_confirmacion_voz(
                    f"El bloque {nombres_str} toca el borde {direccion}. ¿Quieres ampliar el programa haciendo otra foto?",
                    es_pregunta_abierta=False
                )
                
                if "sí" in respuesta or "si" in respuesta:
                    self.estoy_ampliando = True
                    GestorVoz.leer_texto(f"De acuerdo. Pon el bloque {nombres_str} en la nueva foto para usarlo de referencia. Pulsa capturar cuando estés listo.")
                    return 
                else:
                    GestorVoz.leer_texto("De acuerdo, cancelando el resto de ampliaciones y procesando el programa.")
                    self.cola_ampliaciones.clear()
                    
            self.estoy_ampliando = False
            self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo) 
            self._guardar_estado()
            QTimer.singleShot(0, self.leer_codigo_generado)
            
        threading.Thread(target=logica_voz_expansion, daemon=True).start()

    def actualizar_iconos(self, modo_alto_contraste):
        self.modo_alto_contraste = modo_alto_contraste
        if modo_alto_contraste:
            # Rutas a los iconos de alto contraste
            ruta_editar = os.path.join(self.icons_dir, "edit_cont.png")
            ruta_rotar = os.path.join(self.icons_dir, "sync_cont.png")
            ruta_apagar = os.path.join(self.icons_dir, "on-off-button_cont.png")
        else:
            # Rutas a los iconos normales
            ruta_editar = os.path.join(self.icons_dir, "edit.png")
            ruta_rotar = os.path.join(self.icons_dir, "sync.png")
            ruta_apagar = os.path.join(self.icons_dir, "on-off-button.png")
            
        # Reasignamos los iconos a los botones existentes
        self.btn_editar.setIcon(QIcon(ruta_editar))
        self.btn_rotar.setIcon(QIcon(ruta_rotar))
        self.btn_apagar.setIcon(QIcon(ruta_apagar))

    def accion_enviar(self):
        GestorVoz.leer_texto("Subiendo el programa a la placa Micro:bit.")
        self.traductor.subir(self.ruta_codigo)
    
    # --- ACTUALIZADAS PARA EL CONTROL DEL HILO ---
    def accion_rotar_camara(self):
        self.rotar_camara = not self.rotar_camara
        if hasattr(self, 'hilo_camara'):
            self.hilo_camara.rotar = self.rotar_camara

    def accion_apagar_camara(self):
        self.apagar_camara = not self.apagar_camara
        if self.apagar_camara:
            if hasattr(self, 'hilo_camara') and self.hilo_camara.isRunning():
                self.hilo_camara.stop()
            self.vision.liberar_camara()
            self.video_label.clear() 
            self.status_label.setText("Estado: Cámara Apagada")
        else:
            self.vision.iniciar_camara(self.combo_camaras.currentData())
            if hasattr(self, 'hilo_camara'):
                self.hilo_camara.corriendo = True
                self.hilo_camara.start()
            self.status_label.setText("Estado: Cámara Activa")

    def accion_cambiar_camara(self, index):
        if not self.apagar_camara:
            if hasattr(self, 'hilo_camara') and self.hilo_camara.isRunning():
                self.hilo_camara.stop()
            self.vision.liberar_camara()
            self.video_label.clear() 
            id_real = self.combo_camaras.itemData(index)
            self.vision.iniciar_camara(id_real)
            if hasattr(self, 'hilo_camara'):
                self.hilo_camara.corriendo = True
                self.hilo_camara.start()

    # --- NUEVO: Usamos el motor espacial para asegurar el orden de lectura ---
    def accion_leer_qrs_pantalla(self):
        if not hasattr(self, 'frame_actual_bgr'):
            GestorVoz.leer_texto("La cámara no está activa.")
            return
            
        # Hacemos una captura "fantasma" temporal para aprovechar el motor espacial 
        # que ya sabe ordenar los bloques de arriba a abajo y de izquierda a derecha.
        ruta_temp = os.path.join(self.workspace_dir, "outputs", "temp_leer.jpg")
        self.vision.takePhoto(self.frame_actual_bgr, ruta_temp)
        matriz_ordenada = self.vision.get_command_matrix()
        
        textos_a_leer = []
        for fila in matriz_ordenada:
            for bloque in fila:
                if bloque.strip() != "":
                    clave_busqueda = str(bloque).strip().lower()
                    info_bloque = self.traductor.tabla_simbolos.get(clave_busqueda, {})
                    pronunciacion = info_bloque.get("pronunciacion", str(bloque))
                    textos_a_leer.append(pronunciacion)
                    
        if textos_a_leer:
            GestorVoz.leer_qrs_pantalla(textos_a_leer)
        else:
            GestorVoz.leer_texto("No detecto ningún bloque en la pantalla.")

    def accion_explicar_ia(self):
        def actualizar_estado(texto, color_hex):
            self.status_label.setText(texto)
        threading.Thread(target=lambda: self.ai_manager.explicar_codigo(self.ruta_codigo, actualizar_estado), daemon=True).start()

    def accion_cambiar_tts(self):
        self.idx_tts = (self.idx_tts + 1) % len(self.modos_tts)
        modo_actual = self.modos_tts[self.idx_tts]
        
        self.btn_tts.setText(modo_actual["texto"])
        if hasattr(self.traductor, 'set_modo_tts'):
            self.traductor.set_modo_tts(modo_actual["valor"])
            
        if modo_actual["valor"] == "pc":
            GestorVoz.leer_texto("Modo de voz por ordenador activado.")
        elif modo_actual["valor"] == "placa":
            GestorVoz.leer_texto("Modo de voz en la placa activado.")
        elif modo_actual["valor"] == "apagado":
            GestorVoz.leer_texto("Voz de ejecución desactivada.")

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
            except SyntaxError as e:
                self.status_label.setText(f"Error de Sintaxis en línea {e.lineno}")
                GestorVoz.leer_texto("Atención. Hay un error de sintaxis en el archivo.")

        except FileNotFoundError:
            self.caja_texto.setPlainText("# Archivo no generado de momento.")
            self.status_label.setText("Estado: Esperando captura...")

    def _guardar_codigo_archivo(self):
        nuevo_codigo = self.caja_texto.toPlainText()
        
        if hasattr(self, 'bloque_pitches') and self.bloque_pitches:
            lineas_editadas = nuevo_codigo.split('\n')
            idx_insert = 0
            for i, linea in enumerate(lineas_editadas):
                if linea.startswith("import ") or linea.startswith("from "):
                    idx_insert = i + 1
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
            return False

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
            if self._guardar_codigo_archivo():
                self.modo_edicion = False
                if self.modo_alto_contraste:
                    self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "edit_cont.png")))
                else:
                    self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
                self.caja_texto.setReadOnly(True)
                self.leer_codigo_generado()

    def accion_atajo_guardar(self):
        if self.modo_edicion and self._guardar_codigo_archivo():
            self.modo_edicion = False
            self.btn_editar.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
            self.caja_texto.setReadOnly(True)
            self.leer_codigo_generado()
            self.status_label.setText("Estado: Guardado rápido completado")

    def cleanup(self):
        if hasattr(self, 'hilo_camara') and self.hilo_camara.isRunning():
            self.hilo_camara.stop()
        self.vision.free()

    def pausar_camara(self):
        if hasattr(self, 'hilo_camara') and self.hilo_camara.isRunning():
            self.hilo_camara.stop()
        if hasattr(self.vision, 'liberar_camara'):
            self.vision.liberar_camara()
        self.video_label.clear()

    def reanudar_camara(self):
        if not self.apagar_camara:
            if hasattr(self.vision, 'iniciar_camara'):
                idx = self.combo_camaras.currentData()
                self.vision.iniciar_camara(idx)
            if hasattr(self, 'hilo_camara') and not self.hilo_camara.isRunning():
                self.hilo_camara.corriendo = True
                self.hilo_camara.rotar = self.rotar_camara
                self.hilo_camara.start()

    def _procesar_clic_simple(self, text):
        self.clics = 0
        self.ultima_tecla = None
        GestorVoz.leer_texto(text)

    def _procesar_doble_clic(self, func):
        func()
    
    def _tecla_pulsada(self, tecla_id, text, func):
        if self.modo_edicion: return 
        if self.ultima_tecla != tecla_id:
            if self.timer_clic and self.timer_clic.isActive(): self.timer_clic.stop()
            self.clics = 0
            self.ultima_tecla = tecla_id
            
        self.clics += 1
        if self.clics == 1:
            self.timer_clic = QTimer()
            self.timer_clic.setSingleShot(True)
            self.timer_clic.timeout.connect(lambda: self._procesar_clic_simple(text))
            self.timer_clic.start(400)
        elif self.clics == 2:
            if self.timer_clic and self.timer_clic.isActive(): self.timer_clic.stop()
            self._procesar_doble_clic(func)
            self.clics = 0
            self.ultima_tecla = None