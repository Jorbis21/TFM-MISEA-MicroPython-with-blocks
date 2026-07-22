import os
import time
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

# --- IMPORTACIONES DE MOTORES CORE ---
from core.vision import VisionEngine
from core.translator import MicrobitCompiler
from core.ai_manager import AIManager
from core.voice_control import VoiceCommandManager
from core.serial_manager import SerialMonitor

# --- IMPORTACIONES DE VISTAS (MVC) ---
from gui.tab_camara import TabCamara
from gui.tab_json import TabJSON
from gui.tab_qrs import TabQRs

class AppCamara(QMainWindow):

    senal_voz = pyqtSignal(str)

    def __init__(self, workspace_dir, config_dir, assets_dir):
        super().__init__()
        
        # 1. Configuración de Entorno
        self.setWindowTitle("Micro:bit Accesible - Centro de Control")
        self.resize(1280, 800)
        
        # 2. Inicialización de Motores
        self.vision = VisionEngine()
        self.traductor = MicrobitCompiler(config_dir=config_dir)
        self.ai_manager = AIManager(api_key="AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w")
        self.serial_monitor = SerialMonitor()
        self.serial_monitor.arrancar()

        # 3. Creación del Contenedor de Pestañas
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- NUEVO: GESTOR DE ESTILOS ---
        base_data_dir = os.path.dirname(config_dir)
        self.styles_dir = os.path.join(base_data_dir, 'styles')
        
        self.modo_alto_contraste = False
        self.cargar_tema_actual()
        
        # Atajo provisional de teclado para alternar contraste
        self.atajo_tema = QShortcut(QKeySequence("Ctrl+T"), self)
        self.atajo_tema.activated.connect(self.alternar_contraste)

        # 4. Inyección de las Vistas
        self.vista_camara = TabCamara(workspace_dir, assets_dir, self.vision, self.traductor, self.ai_manager)
        self.vista_camara.parent_window = self  # Enlace para el botón de contraste
        
        self.vista_qrs = TabQRs(workspace_dir, self.traductor)
        self.vista_json = TabJSON(config_dir, self.traductor)

        # 5. Añadir al sistema de pestañas
        self.tabs.addTab(self.vista_camara, "Cámara y Control")
        self.tabs.addTab(self.vista_qrs, "Generador de QRs")
        self.tabs.addTab(self.vista_json, "Editor de Diccionario")
        self.tabs.currentChanged.connect(self._gestionar_estado_camara)

        # 6. Atajos globales
        self.atajo_guardar = QShortcut(QKeySequence("Ctrl+S"), self)
        self.atajo_guardar.activated.connect(self.vista_camara.accion_atajo_guardar)
        
        self.atajo_a = QShortcut(QKeySequence("A"), self)
        self.atajo_a.activated.connect(lambda: self.vista_camara._tecla_pulsada("a", "Tomar foto", self.vista_camara.accion_capturar))
        self.atajo_ñ = QShortcut(QKeySequence("Ñ"), self)
        self.atajo_ñ.activated.connect(lambda: self.vista_camara._tecla_pulsada("ñ", "Tomar foto", self.vista_camara.accion_capturar))
        self.atajo_s = QShortcut(QKeySequence("S"), self)
        self.atajo_s.activated.connect(lambda: self.vista_camara._tecla_pulsada("s", "Enviar a MicroBit", self.vista_camara.accion_enviar))
        self.atajo_l = QShortcut(QKeySequence("L"), self)
        self.atajo_l.activated.connect(lambda: self.vista_camara._tecla_pulsada("l", "Enviar a MicroBit", self.vista_camara.accion_enviar))
        self.atajo_d = QShortcut(QKeySequence("D"), self)
        self.atajo_d.activated.connect(lambda: self.vista_camara._tecla_pulsada("d", "Explicar con IA", self.vista_camara.accion_explicar_ia))
        self.atajo_k = QShortcut(QKeySequence("K"), self)
        self.atajo_k.activated.connect(lambda: self.vista_camara._tecla_pulsada("k", "Explicar con IA", self.vista_camara.accion_explicar_ia))
        self.atajo_f = QShortcut(QKeySequence("F"), self)
        self.atajo_f.activated.connect(lambda: self.vista_camara._tecla_pulsada("f", "Leer QRs Mesa", self.vista_camara.accion_leer_qrs_pantalla))
        self.atajo_j = QShortcut(QKeySequence("J"), self)
        self.atajo_j.activated.connect(lambda: self.vista_camara._tecla_pulsada("j", "Leer QRs Mesa", self.vista_camara.accion_leer_qrs_pantalla))
        self.atajo_g = QShortcut(QKeySequence("G"), self)
        self.atajo_g.activated.connect(lambda: self.vista_camara._tecla_pulsada("g", "Modo de lectura por variable", self.vista_camara.accion_cambiar_tts))
        self.atajo_h = QShortcut(QKeySequence("H"), self)
        self.atajo_h.activated.connect(lambda: self.vista_camara._tecla_pulsada("h", "Modo de lectura por variable", self.vista_camara.accion_cambiar_tts))

        # 7. Motor de Control por Voz
        self.senal_voz.connect(self._ejecutar_comando_voz)
        self.voice_manager = VoiceCommandManager(self.senal_voz.emit, workspace_dir)
        self.traductor.set_voice_manager(self.voice_manager)
        
        # 8. Estado del Teclado (Nuevo sistema Tap/Hold)
        self.espacio_presionado = False
        self.tiempo_presion = 0
        self.clics_espacio = 0
        
        self.timer_espacio = QTimer()
        self.timer_espacio.setSingleShot(True)
        self.timer_espacio.timeout.connect(self._procesar_clics_espacio)

        QApplication.instance().installEventFilter(self)

    def closeEvent(self, event):
        self.vista_camara.cleanup()
        if hasattr(self, 'ai_manager'):
            self.ai_manager.apagar_ollama()
            
        if hasattr(self, 'serial_monitor'):
            self.serial_monitor.detener()
        
        event.accept()

    def _ejecutar_comando_voz(self, comando):
        if comando == "capturar": self.vista_camara.accion_capturar()
        elif comando == "enviar": self.vista_camara.accion_enviar()
        elif comando == "explicar": self.vista_camara.accion_explicar_ia()
        elif comando == "leer": self.vista_camara.accion_leer_qrs_pantalla()
        elif comando == "cambiar_tts": self.vista_camara.accion_cambiar_tts()
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:
            if event.isAutoRepeat(): return True 
            
            foco = self.focusWidget()
            esta_escribiendo = foco and hasattr(foco, 'isReadOnly') and not foco.isReadOnly()
            
            if not esta_escribiendo:
                if not self.espacio_presionado:
                    self.espacio_presionado = True
                    self.tiempo_presion = time.time()
                    self.voice_manager.start_dictation_record()
                return True 
                
        elif event.type() == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Space:
            if event.isAutoRepeat(): return True
            
            foco = self.focusWidget()
            esta_escribiendo = foco and hasattr(foco, 'isReadOnly') and not foco.isReadOnly()
            
            if not esta_escribiendo and self.espacio_presionado:
                self.espacio_presionado = False
                duracion = time.time() - self.tiempo_presion
                
                if duracion < 0.4:
                    self.voice_manager.discard_dictation_record()
                    self.clics_espacio += 1
                    self.timer_espacio.start(400) 
                else:
                    self.clics_espacio = 0
                    self.timer_espacio.stop()
                    self.voice_manager.stop_dictation_and_process()
                
                return True
                
        return super().eventFilter(obj, event)

    def alternar_contraste(self):
        """Alterna el tema y oculta o muestra las pestañas secundarias de forma segura."""
        self.modo_alto_contraste = not self.modo_alto_contraste
        self.cargar_tema_actual()
        
        if self.modo_alto_contraste:
            self.tabs.setCurrentIndex(0)
            
            # Guardamos las referencias y títulos antes de removerlas si no están guardadas
            if self.tabs.count() > 1:
                self.pestaña_qrs_widget = self.tabs.widget(1)
                self.pestaña_qrs_texto = self.tabs.tabText(1)
                self.tabs.removeTab(1)
                
            if self.tabs.count() > 1:
                self.pestaña_json_widget = self.tabs.widget(1)
                self.pestaña_json_texto = self.tabs.tabText(1)
                self.tabs.removeTab(1)
            
            if hasattr(self.vista_camara, 'btn_contraste'):
                self.vista_camara.btn_contraste.setText("👁 Modo Estándar")
        else:
            # Restauramos las pestañas en sus posiciones originales
            if hasattr(self, 'pestaña_qrs_widget') and self.pestaña_qrs_widget:
                self.tabs.insertTab(1, self.pestaña_qrs_widget, self.pestaña_qrs_texto)
                
            if hasattr(self, 'pestaña_json_widget') and self.pestaña_json_widget:
                self.tabs.insertTab(2, self.pestaña_json_widget, self.pestaña_json_texto)
            
            if hasattr(self.vista_camara, 'btn_contraste'):
                self.vista_camara.btn_contraste.setText("👁 Modo Contraste")
        
        from core.audio import GestorVoz
        if self.modo_alto_contraste:
            GestorVoz.leer_texto("Modo de alto contraste activado. Pestañas secundarias ocultas.")
        else:
            GestorVoz.leer_texto("Modo estándar activado.")

    def _procesar_clics_espacio(self):
        taps = self.clics_espacio
        self.clics_espacio = 0
        
        if taps == 1:
            self.voice_manager.set_texto_dictado("no")
        elif taps == 2:
            self.voice_manager.set_texto_dictado("sí")
        elif taps >= 3:
            self.voice_manager.set_texto_dictado("pasar")
            
    def _gestionar_estado_camara(self, index):
        if index == 0:  
            self.vista_camara.reanudar_camara()
        else:
            self.vista_camara.pausar_camara()

    # =========================================================
    # MOTOR DE TEMAS (QSS)
    # =========================================================
    def cargar_tema_actual(self):
        """Carga y aplica el QSS correspondiente desde el disco."""
        archivo = "tema_contraste.qss" if self.modo_alto_contraste else "tema_oscuro.qss"
        ruta_qss = os.path.join(self.styles_dir, archivo)
        
        try:
            with open(ruta_qss, "r", encoding="utf-8") as f:
                # Aplicamos el estilo a TODA la aplicación de golpe
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            print(f"Aviso: No se pudo cargar el archivo CSS {archivo}: {e}")

    def alternar_contraste(self):
        """Alterna el estado booleano y recarga la interfaz."""
        self.modo_alto_contraste = not self.modo_alto_contraste
        self.cargar_tema_actual()
        
        from core.audio import GestorVoz
        if self.modo_alto_contraste:
            GestorVoz.leer_texto("Modo de alto contraste activado.")
        else:
            GestorVoz.leer_texto("Modo estándar activado.")