import os
from PyQt6.QtWidgets import QMainWindow, QTabWidget
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import Qt, pyqtSignal

# --- IMPORTACIONES DE MOTORES CORE ---
from core.vision import VisionEngine
from core.translator import MicrobitCompiler
from core.ai_manager import AIManager
from core.voice_control import VoiceCommandManager

# --- IMPORTACIONES DE VISTAS (MVC) ---
from gui.tab_camara import TabCamara
from gui.tab_json import TabJSON
from gui.tab_qrs import TabQRs

class AppCamara(QMainWindow):

    senal_voz = pyqtSignal(str)

    def __init__(self, workspace_dir, config_dir):
        super().__init__()
        
        # 1. Configuración de Entorno
        self.setWindowTitle("Micro:bit Accesible - Centro de Control")
        self.resize(1280, 800)
        
        # 2. Inicialización de Motores (Back-end)
        # Aquí arrancamos el tracker, el compilador y la cascada de IA
        self.vision = VisionEngine()
        self.traductor = MicrobitCompiler(config_dir=config_dir)
        self.ai_manager = AIManager(api_key="AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w")

        # 3. Creación del Contenedor de Pestañas (Estilo Navegador)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Le damos un toque estético con CSS (QSS) para que las solapas sean grandes y legibles
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
                background-color: #2B2B2B;
                color: #D4D4D4;
                border: 1px solid #3C3C3C;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border-top: 3px solid #0052cc;
            }
            QTabWidget::pane {
                border: 1px solid #3C3C3C;
                background-color: #1E1E1E;
            }
        """)

        # 4. Inyección de las Vistas (Front-end)
        self.vista_camara = TabCamara(workspace_dir, self.vision, self.traductor, self.ai_manager)
        self.vista_qrs = TabQRs(workspace_dir, self.traductor)
        self.vista_json = TabJSON(config_dir, self.traductor)

        # 5. Añadir al sistema de pestañas
        self.tabs.addTab(self.vista_camara, "Cámara y Control")
        self.tabs.addTab(self.vista_qrs, "Generador de QRs")
        self.tabs.addTab(self.vista_json, "Editor de Diccionario")

        # 6. Atajos globales (Ctrl+S / Cmd+S para guardar)
        # En PyQt6 se usa QShortcut, que captura la combinación a nivel de ventana global
        self.atajo_guardar = QShortcut(QKeySequence("Ctrl+S"), self)
        self.atajo_guardar.activated.connect(self.vista_camara.accion_atajo_guardar)
        # Atajos de una sola tecla (A, S, F, J) delegados al sistema de doble clic
        self.atajo_a = QShortcut(QKeySequence("A"), self)
        self.atajo_a.activated.connect(lambda: self.vista_camara._tecla_pulsada("a", "Tomar foto", self.vista_camara.accion_capturar))

        self.atajo_s = QShortcut(QKeySequence("S"), self)
        self.atajo_s.activated.connect(lambda: self.vista_camara._tecla_pulsada("s", "Enviar a MicroBit", self.vista_camara.accion_enviar))

        self.atajo_f = QShortcut(QKeySequence("F"), self)
        self.atajo_f.activated.connect(lambda: self.vista_camara._tecla_pulsada("f", "Explicar con IA", self.vista_camara.accion_explicar_ia))

        self.atajo_j = QShortcut(QKeySequence("J"), self)
        self.atajo_j.activated.connect(lambda: self.vista_camara._tecla_pulsada("j", "Leer QRs Mesa", self.vista_camara.accion_leer_qrs_pantalla))

        # 7. Motor de Control por Voz
        # Conectamos nuestra señal segura a la función que ejecuta las acciones
        self.senal_voz.connect(self._ejecutar_comando_voz)
        
        # Le pasamos al motor de voz la capacidad de "tocar el timbre" (emit)
        self.voice_manager = VoiceCommandManager(self.senal_voz.emit, workspace_dir)

    def closeEvent(self, event):
        """
        Se ejecuta automáticamente al pulsar la X de la ventana.
        Crucial para liberar la webcam y evitar que el proceso se quede colgado en RAM.
        """
        self.vista_camara.cleanup()
        event.accept()

    def _ejecutar_comando_voz(self, comando):
        """Redirige la orden detectada por Whisper a la pestaña correspondiente."""
        if comando == "capturar":
            self.vista_camara.accion_capturar()
        elif comando == "enviar":
            self.vista_camara.accion_enviar()
        elif comando == "explicar":
            self.vista_camara.accion_explicar_ia()
        elif comando == "leer":
            self.vista_camara.accion_leer_qrs_pantalla()

    def keyPressEvent(self, event):
        """Filtro global para capturar la barra espaciadora como botón de escucha."""
        foco = self.focusWidget()
        es_caja_texto = foco and foco.__class__.__name__ in ['QLineEdit', 'QTextEdit', 'QPlainTextEdit']
        
        if event.key() == Qt.Key.Key_Space and not es_caja_texto:
            self.voice_manager.toggle_recording()
        else:
            # Si era otra tecla, o estamos dentro del editor de código, dejamos que actúe normal
            super().keyPressEvent(event)