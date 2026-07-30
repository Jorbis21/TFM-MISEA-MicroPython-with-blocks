import os, time
from PyQt6.QtGui import QShortcut, QKeySequence, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QPushButton

from core.vision import VisionEngine
from core.translator import MicrobitCompiler
from core.ai_manager import AIManager
from core.voice_control import VoiceCommandManager
from core.serial_manager import SerialMonitor
from core.audio import GestorVoz 

from gui.tab_camara import TabCamara
from gui.tab_json import TabJSON
from gui.tab_qrs import TabQRs

from utils.constants import TipoEvento
from core.voice_control import EventoInteraccion

class AppCamara(QMainWindow):

    senal_voz = pyqtSignal(str)# A lo mejor hay que cambiar el str por object

    def __init__(self, workspace_dir, config_dir, assets_dir):
        super().__init__()

        self.vista_camara = None
        self.vista_qrs = None
        self.vista_json = None
        self.ai_manager = None
        self.serial_monitor = None
        self.hilo_camara = None
        
        self.setWindowTitle("ONCE: MicroPython por bloques")
        self.setWindowIcon(QIcon(os.path.join(assets_dir, "icons", "once.png")))
        self.resize(1280, 800)
        
        self.vision = VisionEngine()
        self.traductor = MicrobitCompiler(config_dir)
        self.ai_manager = AIManager("AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w")
        self.serial_monitor = SerialMonitor()
        self.serial_monitor.arrancar()

        self.tabs = QTabWidget()
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCentralWidget(self.tabs)

        base_data_dir = os.path.dirname(config_dir)
        self.styles_dir = os.path.join(base_data_dir, 'styles')
        
        self.modo_alto_contraste = True
        
        self.atajo_tema = QShortcut(QKeySequence("Ctrl+T"), self)
        self.atajo_tema.activated.connect(self.alternar_contraste)

        self.vista_camara = TabCamara(workspace_dir, assets_dir, self.vision, self.traductor, self.ai_manager)
        self.vista_camara.parent_window = self  
        
        self.vista_qrs = TabQRs(workspace_dir, self.traductor)
        self.vista_json = TabJSON(config_dir, self.traductor, assets_dir)

        self.btn_contraste = QPushButton("Modo Contraste")
        self.btn_contraste.setObjectName("btn_contraste")
        self.btn_contraste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_contraste.clicked.connect(self.alternar_contraste)

        self.tabs.setCornerWidget(self.btn_contraste, Qt.Corner.TopRightCorner)

        self.tabs.addTab(self.vista_camara, "Cámara y Control")
        self.tabs.addTab(self.vista_qrs, "Generador de QRs")
        self.tabs.addTab(self.vista_json, "Editor de Diccionario")
        self.tabs.currentChanged.connect(self._gestionar_estado_camara)

        self._aplicar_estado_contraste(silencioso=True)

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
        self.atajo_v = QShortcut(QKeySequence("V"), self)
        self.atajo_v.activated.connect(lambda: self.vista_camara._tecla_pulsada("v", "Modificar variables", self.vista_camara.accion_repasar_variables))
        self.atajo_n = QShortcut(QKeySequence("N"), self)
        self.atajo_n.activated.connect(lambda: self.vista_camara._tecla_pulsada("n", "Modificar variables", self.vista_camara.accion_repasar_variables))

        self.senal_voz.connect(self._ejecutar_comando_voz)
        
        self.voice_manager = VoiceCommandManager(self.senal_voz.emit, workspace_dir, self.bloquear_interfaz)
        self.traductor.set_voice_manager(self.voice_manager)
        
        self.espacio_presionado = False
        self.tiempo_presion = 0
        self.clics_espacio = 0
        
        self.timer_espacio = QTimer()
        self.timer_espacio.setSingleShot(True)
        self.timer_espacio.timeout.connect(self._procesar_clics_espacio)

        QApplication.instance().installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._al_cambiar_foco)

    '''Hace la lectura de los botones dependiendo de cual este seleccionado'''
    def _al_cambiar_foco(self, old_widget, new_widget):
        if not old_widget or not new_widget: return
        if self.tabs.currentIndex() != 0: return

        if isinstance(new_widget, QPushButton):
            nombre_obj = new_widget.objectName()
            
            if nombre_obj == "btn_contraste" or nombre_obj == "combo_camaras" or nombre_obj == "btn_editar":
                return
                
            texto = new_widget.text().strip()
            
            if nombre_obj == "btn_overlay":
                if new_widget == self.vista_camara.btn_rotar:
                    texto = "Rotar cámara"
                elif new_widget == self.vista_camara.btn_apagar:
                    texto = "Apagar cámara"
            
            if texto:
                GestorVoz.leer_texto_interrumpiendo(texto)

    '''Gestiona el uso del espacio contando las veces que se pulsa'''
    def _procesar_clics_espacio(self):
        taps = self.clics_espacio
        self.clics_espacio = 0
        
        if taps == 1:
            evento = EventoInteraccion(tipo=TipoEvento.TOQUE_FISICO, es_afirmativo=False)
            self.voice_manager.inyectar_evento(evento)
        elif taps == 2:
            evento = EventoInteraccion(tipo=TipoEvento.TOQUE_FISICO, es_afirmativo=True)
            self.voice_manager.inyectar_evento(evento)
        elif taps >= 3:
            evento = EventoInteraccion(tipo=TipoEvento.OMITIR)
            self.voice_manager.inyectar_evento(evento)

    '''Enciende o apaga la camara segun en la pestaña en la que estes'''
    def _gestionar_estado_camara(self, index):
        if index == 0:  
            self.vista_camara.reanudar_camara()
        else:
            self.vista_camara.pausar_camara()

    '''Cambia el estilo y oculta las pestañas'''
    def _aplicar_estado_contraste(self, silencioso=False):
        self.cargar_tema_actual()
        
        if self.modo_alto_contraste:
            self.tabs.setCurrentIndex(0)
            
            if self.tabs.count() == 3:
                self.tabs.removeTab(2)
                self.tabs.removeTab(1)
            
            if self.btn_contraste is not None:
                self.btn_contraste.setText("Modo Estándar")
                
            if not silencioso:
                GestorVoz.leer_texto("Modo de alto contraste activado.")
        else:

            if self.tabs.count() == 1:
                if self.vista_qrs is not None:
                    self.tabs.addTab(self.vista_qrs, "Generador de QRs")
                    
                if self.vista_json is not None:
                    self.tabs.addTab(self.vista_json, "Editor de Diccionario")
            
            if self.btn_contraste is not None:
                self.btn_contraste.setText("Modo Contraste")
                
            if not silencioso:
                GestorVoz.leer_texto("Modo estándar activado.")

    '''Bloquea la gui para no interrumpir procesos'''
    def bloquear_interfaz(self, bloquear):
        self.tabs.setEnabled(not bloquear)
        if self.vista_camara is not None:
            if bloquear:
                self.vista_camara.status_label.setText("Estado: Interfaz bloqueada (Esperando respuesta por voz...)")
            else:
                self.vista_camara.status_label.setText("Estado: Cámara Activa")

    '''Ejecuta la accion segun el comando de voz recibido'''
    def _ejecutar_comando_voz(self, comando):
        if comando == "capturar": self.vista_camara.accion_capturar()
        elif comando == "enviar": self.vista_camara.accion_enviar()
        elif comando == "explicar": self.vista_camara.accion_explicar_ia()
        elif comando == "leer": self.vista_camara.accion_leer_qrs_pantalla()
        elif comando == "cambiar_tts": self.vista_camara.accion_cambiar_tts()
        elif comando == "repasar": self.vista_camara.accion_repasar_variables()

    '''Cierra los hilos y servicios externos al cerrar el programa'''
    def closeEvent(self, event):
        if self.vista_camara is not None:
            self.vista_camara.cleanup()
            
        if self.ai_manager is not None:
            self.ai_manager.apagar_ollama()
            
        if self.serial_monitor is not None:
            self.serial_monitor.detener()
        
        event.accept()
        
    def eventFilter(self, obj, event):
        # 1. Filtramos solo los eventos que nos interesan (presionar o soltar teclas)
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            foco = self.focusWidget()
            
            # 2. Lógica EAFP: Intentamos leer el estado en lugar de usar hasattr
            esta_escribiendo = False
            if foco is not None:
                try:
                    esta_escribiendo = not foco.isReadOnly()
                except AttributeError:
                    pass # El widget no tiene el método isReadOnly(), no es de texto
            
            # Si el usuario está escribiendo, no interceptamos nada y dejamos que PyQt actúe
            if not esta_escribiendo:
                
                # --- EVENTOS AL PRESIONAR LA TECLA ---
                if event.type() == QEvent.Type.KeyPress:
                    
                    if event.key() == Qt.Key.Key_Space:
                        if event.isAutoRepeat(): 
                            return True 
                        
                        if not self.espacio_presionado:
                            self.espacio_presionado = True
                            self.tiempo_presion = time.time()
                            self.voice_manager.start_dictation_record()
                        return True 
                    
                    elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
                        self.focusNextChild()
                        return True
                        
                    elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
                        self.focusPreviousChild()
                        return True
                        
                    elif event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                        # Lógica EAFP: En lugar de isinstance(foco, QPushButton), 
                        # intentamos hacer click() y perdonamos si falla.
                        if foco is not None:
                            try:
                                foco.click()
                                return True
                            except AttributeError:
                                pass

                # --- EVENTOS AL SOLTAR LA TECLA ---
                elif event.type() == QEvent.Type.KeyRelease:
                    
                    if event.key() == Qt.Key.Key_Space:
                        if event.isAutoRepeat(): 
                            return True
                        
                        if self.espacio_presionado:
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
                            
        # Si no se cumple ninguna de nuestras reglas, el evento sigue su curso normal
        return super().eventFilter(obj, event)

    '''Carga el tema correspondiente'''
    def cargar_tema_actual(self):
        archivo = "tema_contraste.qss" if self.modo_alto_contraste else "tema_oscuro.qss"
        ruta_qss = os.path.join(self.styles_dir, archivo)
        try:
            with open(ruta_qss, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            print(f"Aviso: No se pudo cargar el archivo CSS {archivo}: {e}")

    '''Hace el cambio de estilos al pulsar el boton de contraste'''
    def alternar_contraste(self):
        self.modo_alto_contraste = not self.modo_alto_contraste
        self._aplicar_estado_contraste(silencioso=False)
        self.vista_camara.actualizar_iconos(self.modo_alto_contraste)