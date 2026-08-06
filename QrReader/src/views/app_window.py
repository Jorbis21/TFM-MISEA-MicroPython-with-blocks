import os

from PyQt6.QtGui import QShortcut, QKeySequence, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QPushButton

from views.tab_camara import TabCamara
from views.tab_json import TabJSON
from views.tab_qrs import TabQRs

class AppCamara(QMainWindow):

    # Señales puras para comunicarse con el Controlador
    spacebar_pressed = pyqtSignal()
    spacebar_released = pyqtSignal()
    shortcut_command = pyqtSignal(str)
    changed_focus = pyqtSignal(str) # Avisa para que el controlador hable
    window_closed = pyqtSignal()

    def __init__(self, workspace_dir, assets_dir, camara_ctrl, json_ctrl, qr_ctrl):
        super().__init__()
        
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

        self.vista_camara = TabCamara(workspace_dir, assets_dir, camara_ctrl)
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
        self._configurar_atajos()

        # Variables de estado puras de la interfaz
        self.espacio_mantenido = False

        QApplication.instance().installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._al_cambiar_foco)

    def _configurar_atajos(self):
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.vista_camara.accion_atajo_guardar)
        
        # Restauramos la lógica de 1 toque (leer) y 2 toques (acción) pasando por la vista_camara
        QShortcut(QKeySequence("A"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("a", "Tomar foto", self.vista_camara.accion_capturar))
        QShortcut(QKeySequence("Ñ"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("ñ", "Tomar foto", self.vista_camara.accion_capturar))
        
        QShortcut(QKeySequence("S"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("s", "Enviar a MicroBit", self.vista_camara.accion_enviar))
        QShortcut(QKeySequence("L"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("l", "Enviar a MicroBit", self.vista_camara.accion_enviar))
        
        QShortcut(QKeySequence("D"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("d", "Explicar con IA", self.vista_camara.accion_explicar_ia))
        QShortcut(QKeySequence("K"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("k", "Explicar con IA", self.vista_camara.accion_explicar_ia))
        
        QShortcut(QKeySequence("F"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("f", "Leer QRs Mesa", self.vista_camara.accion_leer_qrs_pantalla))
        QShortcut(QKeySequence("J"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("j", "Leer QRs Mesa", self.vista_camara.accion_leer_qrs_pantalla))
        
        QShortcut(QKeySequence("G"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("g", "Modo de lectura por variable", self.vista_camara.accion_cambiar_tts))
        QShortcut(QKeySequence("H"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("h", "Modo de lectura por variable", self.vista_camara.accion_cambiar_tts))
        
        QShortcut(QKeySequence("V"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("v", "Modificar variables", self.vista_camara.accion_repasar_variables))
        QShortcut(QKeySequence("N"), self).activated.connect(lambda: self.vista_camara.procesar_atajo_teclado("n", "Modificar variables", self.vista_camara.accion_repasar_variables))

    def _al_cambiar_foco(self, old_widget, new_widget):
        if not old_widget or not new_widget: return
        if self.tabs.currentIndex() != 0: return

        if isinstance(new_widget, QPushButton):
            nombre_obj = new_widget.objectName()
            if nombre_obj in ["btn_contraste", "combo_camaras", "btn_editar"]: return
                
            texto = new_widget.text().strip()
            if nombre_obj == "btn_overlay":
                if new_widget == self.vista_camara.btn_rotar: texto = "Rotar cámara"
                elif new_widget == self.vista_camara.btn_apagar: texto = "Apagar cámara"
            
            if texto:
                self.changed_focus.emit(texto)

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
            if not silencioso: 
                self.changed_focus.emit("Modo de alto contraste activado.")
        else:
            if self.tabs.count() == 1:
                self.tabs.addTab(self.vista_qrs, "Generador de QRs")
                self.tabs.addTab(self.vista_json, "Editor de Diccionario")
            self.btn_contraste.setText("Modo Contraste")
            if not silencioso: 
                self.changed_focus.emit("Modo estándar activado.")

    def alternar_contraste(self):
        self.modo_alto_contraste = not self.modo_alto_contraste
        self._aplicar_estado_contraste(silencioso=False)
        self.vista_camara.actualizar_iconos(self.modo_alto_contraste)

    def freeze_ui(self, freeze):
        self.tabs.setEnabled(not freeze)
        if freeze: 
            self.vista_camara.status_label.setText("Estado: Interfaz bloqueada (Esperando respuesta por voz...)")
        else: 
            self.vista_camara.status_label.setText("Estado: Cámara Activa")

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
                        
                        if not self.espacio_mantenido:
                            self.espacio_mantenido = True
                            self.spacebar_pressed.emit()
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
                        
                        if self.espacio_mantenido:
                            self.espacio_mantenido = False
                            self.spacebar_released.emit()
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

    def closeEvent(self, event):
        if self.vista_camara is not None:
            self.vista_camara.cleanup()
        self.window_closed.emit()
        event.accept()