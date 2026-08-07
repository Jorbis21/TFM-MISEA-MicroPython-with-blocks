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

    def __init__(self, workspace_dir, assets_dir, camera_ctrl, json_ctrl, qr_ctrl):
        super().__init__()
        
        self.setWindowTitle("ONCE: MicroPython por bloques")
        self.setWindowIcon(QIcon(os.path.join(assets_dir, "icons", "once.png")))
        self.resize(1280, 800)

        self.tabs = QTabWidget()
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCentralWidget(self.tabs)

        self.styles_dir = os.path.abspath(os.path.join(assets_dir, '..', 'styles'))
        self.high_contrast_mode = True
        
        self.theme_contrast = QShortcut(QKeySequence("Ctrl+T"), self)
        self.theme_contrast.activated.connect(self.change_contrast)

        self.camera_view = TabCamara(workspace_dir, assets_dir, camera_ctrl)
        self.camera_view.parent_window = self  
        
        self.qr_view = TabQRs(qr_ctrl)
        self.json_view = TabJSON(json_ctrl, assets_dir)

        self.contrast_btn = QPushButton("Modo Contraste")
        self.contrast_btn.setObjectName("btn_contraste")
        self.contrast_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.contrast_btn.clicked.connect(self.change_contrast)

        self.tabs.setCornerWidget(self.contrast_btn, Qt.Corner.TopRightCorner)

        self.tabs.addTab(self.camera_view, "Cámara y Control")
        self.tabs.addTab(self.qr_view, "Generador de QRs")
        self.tabs.addTab(self.json_view, "Editor de Diccionario")
        self.tabs.currentChanged.connect(self._manage_camera_state)

        self._set_contrast_state(silencioso=True)
        self._configure_shortcuts()

        # Variables de estado puras de la interfaz
        self.holded_space = False

        QApplication.instance().installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def _configure_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.camera_view.accion_atajo_guardar)
        
        # Restauramos la lógica de 1 toque (leer) y 2 toques (acción) pasando por la vista_camara
        QShortcut(QKeySequence("A"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("a", "Tomar foto", self.camera_view.action_capture))
        QShortcut(QKeySequence("Ñ"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("ñ", "Tomar foto", self.camera_view.action_capture))
        
        QShortcut(QKeySequence("S"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("s", "Enviar a MicroBit", self.camera_view.action_send))
        QShortcut(QKeySequence("L"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("l", "Enviar a MicroBit", self.camera_view.action_send))
        
        QShortcut(QKeySequence("D"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("d", "Explicar con IA", self.camera_view.action_ia_explain))
        QShortcut(QKeySequence("K"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("k", "Explicar con IA", self.camera_view.action_ia_explain))
        
        QShortcut(QKeySequence("F"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("f", "Leer QRs Mesa", self.camera_view.action_read_qrs))
        QShortcut(QKeySequence("J"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("j", "Leer QRs Mesa", self.camera_view.action_read_qrs))
        
        QShortcut(QKeySequence("G"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("g", "Modo de lectura por variable", self.camera_view.action_change_tts))
        QShortcut(QKeySequence("H"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("h", "Modo de lectura por variable", self.camera_view.action_change_tts))
        
        QShortcut(QKeySequence("V"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("v", "Modificar variables", self.camera_view.action_var_review))
        QShortcut(QKeySequence("N"), self).activated.connect(lambda: self.camera_view.procesar_atajo_teclado("n", "Modificar variables", self.camera_view.action_var_review))

    def _on_focus_changed(self, old_widget, new_widget):
        if not old_widget or not new_widget: return
        if self.tabs.currentIndex() != 0: return

        if isinstance(new_widget, QPushButton):
            nombre_obj = new_widget.objectName()
            if nombre_obj in ["btn_contraste", "combo_camaras", "btn_editar"]: return
                
            texto = new_widget.text().strip()
            if nombre_obj == "btn_overlay":
                if new_widget == self.camera_view.btn_rotar: texto = "Rotar cámara"
                elif new_widget == self.camera_view.btn_apagar: texto = "Apagar cámara"
            
            if texto:
                self.changed_focus.emit(texto)

    def _manage_camera_state(self, index):
        if index == 0: self.camera_view.reanudar_camara()
        else: self.camera_view.pausar_camara()

    def _set_contrast_state(self, silencioso=False):
        self.cargar_tema_actual()
        
        if self.high_contrast_mode:
            self.tabs.setCurrentIndex(0)
            if self.tabs.count() == 3:
                self.tabs.removeTab(2)
                self.tabs.removeTab(1)
            self.contrast_btn.setText("Modo Estándar")
            if not silencioso: 
                self.changed_focus.emit("Modo de alto contraste activado.")
        else:
            if self.tabs.count() == 1:
                self.tabs.addTab(self.qr_view, "Generador de QRs")
                self.tabs.addTab(self.json_view, "Editor de Diccionario")
            self.contrast_btn.setText("Modo Contraste")
            if not silencioso: 
                self.changed_focus.emit("Modo estándar activado.")

    def change_contrast(self):
        self.high_contrast_mode = not self.high_contrast_mode
        self._set_contrast_state(silencioso=False)
        self.camera_view.actualizar_iconos(self.high_contrast_mode)

    def freeze_ui(self, freeze):
        self.tabs.setEnabled(not freeze)
        if freeze: 
            self.camera_view.status_label.setText("Estado: Interfaz bloqueada (Esperando respuesta por voz...)")
        else: 
            self.camera_view.status_label.setText("Estado: Cámara Activa")

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
                        
                        if not self.holded_space:
                            self.holded_space = True
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
                        
                        if self.holded_space:
                            self.holded_space = False
                            self.spacebar_released.emit()
                            return True
                        
        return super().eventFilter(obj, event)

    def cargar_tema_actual(self):
        archivo = "tema_contraste.qss" if self.high_contrast_mode else "tema_oscuro.qss"
        ruta_qss = os.path.join(self.styles_dir, archivo)
        try:
            with open(ruta_qss, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            print(f"Aviso: No se pudo cargar el archivo CSS {archivo}: {e}")

    def closeEvent(self, event):
        if self.camera_view is not None:
            self.camera_view.cleanup()
        self.window_closed.emit()
        event.accept()