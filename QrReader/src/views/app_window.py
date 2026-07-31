import os, time
from PyQt6.QtGui import QShortcut, QKeySequence, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QPushButton

from models.voice_control import VoiceCommandManager
from models.audio import GestorVoz 
from views.tab_camara import TabCamara
from views.tab_json import TabJSON
from views.tab_qrs import TabQRs
from utils.constants import TipoEvento
from models.voice_control import EventoInteraccion
# Cámbialo para que quede así:
from utils.constants import TipoEvento, ComandoVoz

class AppCamara(QMainWindow):

    senal_voz = pyqtSignal(object)

    def __init__(self, workspace_dir, assets_dir, camara_ctrl, json_ctrl, qr_ctrl, vision, ai_manager, traductor, app_ctrl):
        super().__init__()
        self.app_ctrl = app_ctrl
        
        self.setWindowTitle("ONCE: MicroPython por bloques")
        self.setWindowIcon(QIcon(os.path.join(assets_dir, "icons", "once.png")))
        self.resize(1280, 800)

        self.tabs = QTabWidget()
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCentralWidget(self.tabs)

        self.styles_dir = os.path.abspath(os.path.join(assets_dir, '..', 'styles'))
        self.modo_alto_contraste = True
        
        self.atajo_tema = QShortcut(QKeySequence("Ctrl+T"), self)
        self.atajo_tema.activated.connect(self.alternar_contraste)

        self.vista_camara = TabCamara(workspace_dir, assets_dir, camara_ctrl, vision, ai_manager)
        self.vista_camara.parent_window = self  
        
        self.vista_qrs = TabQRs(qr_ctrl)
        self.vista_json = TabJSON(json_ctrl, assets_dir)

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
        self.atajo_a.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("a", "Tomar foto", self.vista_camara.accion_capturar))
        self.atajo_ñ = QShortcut(QKeySequence("Ñ"), self)
        self.atajo_ñ.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("ñ", "Tomar foto", self.vista_camara.accion_capturar))
        self.atajo_s = QShortcut(QKeySequence("S"), self)
        self.atajo_s.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("s", "Enviar a MicroBit", self.vista_camara.accion_enviar))
        self.atajo_l = QShortcut(QKeySequence("L"), self)
        self.atajo_l.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("l", "Enviar a MicroBit", self.vista_camara.accion_enviar))
        self.atajo_d = QShortcut(QKeySequence("D"), self)
        self.atajo_d.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("d", "Explicar con IA", self.vista_camara.accion_explicar_ia))
        self.atajo_k = QShortcut(QKeySequence("K"), self)
        self.atajo_k.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("k", "Explicar con IA", self.vista_camara.accion_explicar_ia))
        self.atajo_f = QShortcut(QKeySequence("F"), self)
        self.atajo_f.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("f", "Leer QRs Mesa", self.vista_camara.accion_leer_qrs_pantalla))
        self.atajo_j = QShortcut(QKeySequence("J"), self)
        self.atajo_j.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("j", "Leer QRs Mesa", self.vista_camara.accion_leer_qrs_pantalla))
        self.atajo_g = QShortcut(QKeySequence("G"), self)
        self.atajo_g.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("g", "Modo de lectura por variable", self.vista_camara.accion_cambiar_tts))
        self.atajo_h = QShortcut(QKeySequence("H"), self)
        self.atajo_h.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("h", "Modo de lectura por variable", self.vista_camara.accion_cambiar_tts))
        self.atajo_v = QShortcut(QKeySequence("V"), self)
        self.atajo_v.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("v", "Modificar variables", self.vista_camara.accion_repasar_variables))
        self.atajo_n = QShortcut(QKeySequence("N"), self)
        self.atajo_n.activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("n", "Modificar variables", self.vista_camara.accion_repasar_variables))
        
        self.senal_voz.connect(self._ejecutar_comando_voz)
        
        self.voice_manager = VoiceCommandManager(self.senal_voz.emit, workspace_dir, self.bloquear_interfaz)
        traductor.set_voice_manager(self.voice_manager)
        
        self.espacio_presionado = False
        self.tiempo_presion = 0
        self.clics_espacio = 0
        
        self.timer_espacio = QTimer()
        self.timer_espacio.setSingleShot(True)
        self.timer_espacio.timeout.connect(self._procesar_clics_espacio)

        QApplication.instance().installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._al_cambiar_foco)

    def _al_cambiar_foco(self, old_widget, new_widget):
        if not old_widget or not new_widget: return
        if self.tabs.currentIndex() != 0: return

        if isinstance(new_widget, QPushButton):
            nombre_obj = new_widget.objectName()
            if nombre_obj == "btn_contraste" or nombre_obj == "combo_camaras" or nombre_obj == "btn_editar": return
                
            texto = new_widget.text().strip()
            if nombre_obj == "btn_overlay":
                if new_widget == self.vista_camara.btn_rotar: texto = "Rotar cámara"
                elif new_widget == self.vista_camara.btn_apagar: texto = "Apagar cámara"
            
            if texto: GestorVoz.leer_texto_interrumpiendo(texto)

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

    def _gestionar_estado_camara(self, index):
        if index == 0: self.vista_camara.reanudar_camara()
        else: self.vista_camara.pausar_camara()

    def _aplicar_estado_contraste(self, silencioso=False):
        self.cargar_tema_actual()
        
        if self.modo_alto_contraste:
            self.tabs.setCurrentIndex(0)
            if self.tabs.count() == 3:
                self.tabs.removeTab(2)
                self.tabs.removeTab(1)
            self.btn_contraste.setText("Modo Estándar")
            if not silencioso: GestorVoz.leer_texto("Modo de alto contraste activado.")
        else:
            if self.tabs.count() == 1:
                self.tabs.addTab(self.vista_qrs, "Generador de QRs")
                self.tabs.addTab(self.vista_json, "Editor de Diccionario")
            self.btn_contraste.setText("Modo Contraste")
            if not silencioso: GestorVoz.leer_texto("Modo estándar activado.")

    def bloquear_interfaz(self, bloquear):
        self.tabs.setEnabled(not bloquear)
        if bloquear: self.vista_camara.status_label.setText("Estado: Interfaz bloqueada (Esperando respuesta por voz...)")
        else: self.vista_camara.status_label.setText("Estado: Cámara Activa")

    def _ejecutar_comando_voz(self, comando):
        if comando == ComandoVoz.CAPTURAR: self.vista_camara.accion_capturar()
        elif comando == ComandoVoz.ENVIAR: self.vista_camara.accion_enviar()
        elif comando == ComandoVoz.EXPLICAR: self.vista_camara.accion_explicar_ia()
        elif comando == ComandoVoz.LEER: self.vista_camara.accion_leer_qrs_pantalla()
        elif comando == ComandoVoz.CAMBIAR_TTS: self.vista_camara.accion_cambiar_tts()
        elif comando == ComandoVoz.REPASAR: self.vista_camara.accion_repasar_variables()

    def closeEvent(self, event):
        if self.vista_camara is not None:
            self.vista_camara.cleanup()
            
        # El controlador de la aplicación apaga los demonios
        if self.app_ctrl is not None:
            self.app_ctrl.apagar_sistema()
        
        event.accept()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            foco = self.focusWidget()
            esta_escribiendo = False
            if foco is not None:
                try: esta_escribiendo = not foco.isReadOnly()
                except AttributeError: pass 

            if not esta_escribiendo:
                if event.type() == QEvent.Type.KeyPress:
                    if event.key() == Qt.Key.Key_Space:
                        if event.isAutoRepeat(): return True 
                        
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
                        if foco is not None:
                            try:
                                foco.click()
                                return True
                            except AttributeError: pass

                elif event.type() == QEvent.Type.KeyRelease:
                    if event.key() == Qt.Key.Key_Space:
                        if event.isAutoRepeat(): return True
                        
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
                        
        return super().eventFilter(obj, event)

    def cargar_tema_actual(self):
        archivo = "tema_contraste.qss" if self.modo_alto_contraste else "tema_oscuro.qss"
        ruta_qss = os.path.join(self.styles_dir, archivo)
        try:
            with open(ruta_qss, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            print(f"Aviso: No se pudo cargar el archivo CSS {archivo}: {e}")

    def alternar_contraste(self):
        self.modo_alto_contraste = not self.modo_alto_contraste
        self._aplicar_estado_contraste(silencioso=False)
        self.vista_camara.actualizar_iconos(self.modo_alto_contraste)