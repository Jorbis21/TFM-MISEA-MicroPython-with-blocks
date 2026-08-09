import os

from PyQt6.QtGui import QShortcut, QKeySequence, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QPushButton

from views.tab_camara import TabCamara
from views.tab_json import TabJSON
from views.tab_qrs import TabQRs

class AppCamara(QMainWindow):

    spacebar_pressed = pyqtSignal()
    spacebar_released = pyqtSignal()
    shortcut_command = pyqtSignal(str)
    changed_focus = pyqtSignal(str)
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

        self._set_contrast_state(silent=True)
        self._configure_shortcuts()

        self.holded_space = False

        QApplication.instance().installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def change_contrast(self):
        """Cambia el tema"""
        """Changes the theme"""
        self.high_contrast_mode = not self.high_contrast_mode
        self._set_contrast_state(silent=False)
        self.camera_view.update_icons(self.high_contrast_mode)

    def freeze_ui(self, freeze):
        """Congela la interfaz"""
        """Freeze the interface"""
        self.tabs.setEnabled(not freeze)
        if freeze: 
            self.camera_view.status_label.setText("Estado: Interfaz bloqueada (Esperando respuesta por voz...)")
        else: 
            self.camera_view.status_label.setText("Estado: Cámara Activa")

    def eventFilter(self, obj, event):
        """Filtra las pulsaciones del teclado"""
        """Filters the keyboard inputs"""
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            focus = self.focusWidget()
            writing = False
            if focus is not None:
                try: writing = not focus.isReadOnly()
                except AttributeError: pass 

            if not writing:
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
                        if focus is not None:
                            try:
                                focus.click()
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

    def closeEvent(self, event):
        """Cierra todos los sistemas y la ventana"""
        """Closes all the systems and the window"""
        self.camera_view.cleanup()
        self.window_closed.emit()
        event.accept()

    def _configure_shortcuts(self):
        """Configura los diferentes atajos de teclado"""
        """Configures the shortcuts"""
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.camera_view.action_save_shortcut)
        
        QShortcut(QKeySequence("A"), self).activated.connect(lambda: self.camera_view.process_chortcut("a", "Tomar foto", self.camera_view.action_capture))
        QShortcut(QKeySequence("Ñ"), self).activated.connect(lambda: self.camera_view.process_chortcut("ñ", "Tomar foto", self.camera_view.action_capture))
        
        QShortcut(QKeySequence("S"), self).activated.connect(lambda: self.camera_view.process_chortcut("s", "Enviar a MicroBit", self.camera_view.action_send))
        QShortcut(QKeySequence("L"), self).activated.connect(lambda: self.camera_view.process_chortcut("l", "Enviar a MicroBit", self.camera_view.action_send))
        
        QShortcut(QKeySequence("D"), self).activated.connect(lambda: self.camera_view.process_chortcut("d", "Explicar con IA", self.camera_view.action_ia_explain))
        QShortcut(QKeySequence("K"), self).activated.connect(lambda: self.camera_view.process_chortcut("k", "Explicar con IA", self.camera_view.action_ia_explain))
        
        QShortcut(QKeySequence("F"), self).activated.connect(lambda: self.camera_view.process_chortcut("f", "Leer QRs Mesa", self.camera_view.action_read_qrs))
        QShortcut(QKeySequence("J"), self).activated.connect(lambda: self.camera_view.process_chortcut("j", "Leer QRs Mesa", self.camera_view.action_read_qrs))
        
        QShortcut(QKeySequence("G"), self).activated.connect(lambda: self.camera_view.process_chortcut("g", "Modo de lectura por variable", self.camera_view.action_change_tts))
        QShortcut(QKeySequence("H"), self).activated.connect(lambda: self.camera_view.process_chortcut("h", "Modo de lectura por variable", self.camera_view.action_change_tts))
        
        QShortcut(QKeySequence("V"), self).activated.connect(lambda: self.camera_view.process_chortcut("v", "Modificar variables", self.camera_view.action_var_review))
        QShortcut(QKeySequence("N"), self).activated.connect(lambda: self.camera_view.process_chortcut("n", "Modificar variables", self.camera_view.action_var_review))

    def _on_focus_changed(self, old_widget, new_widget):
        """Cambia el foco del boton seleccionado y omite algunos"""
        """Change the focus of the selected button and omit some"""
        if not old_widget or not new_widget: return
        if self.tabs.currentIndex() != 0: return

        if isinstance(new_widget, QPushButton):
            name_obj = new_widget.objectName()
            if name_obj in ["contrast_btn", "combo_cameras", "edit_btn"]: return
                
            text = new_widget.text().strip()
            if name_obj == "overlay_btn":
                if new_widget == self.camera_view.rotate_btn: text = "Rotar cámara"
                elif new_widget == self.camera_view.shutdown_btn: text = "Apagar cámara"
            
            if text:
                self.changed_focus.emit(text)

    def _manage_camera_state(self, index):
        """Maneja el estado de la camara"""
        """Manage the camera state"""
        if index == 0: self.camera_view.resume_camera()
        else: self.camera_view.pause_camera()

    def _set_contrast_state(self, silent=False):
        """Carga el tema correspondiente y quita las pestañas si es el de contraste"""
        """Loads the actual theme and hides the tabs if is the contrast theme"""
        self._load_actual_theme()
        
        if self.high_contrast_mode:
            self.tabs.setCurrentIndex(0)
            if self.tabs.count() == 3:
                self.tabs.removeTab(2)
                self.tabs.removeTab(1)
            self.contrast_btn.setText("Modo Estándar")
            if not silent: 
                self.changed_focus.emit("Modo de alto contraste activado.")
        else:
            if self.tabs.count() == 1:
                self.tabs.addTab(self.qr_view, "Generador de QRs")
                self.tabs.addTab(self.json_view, "Editor de Diccionario")
            self.contrast_btn.setText("Modo Contraste")
            if not silent: 
                self.changed_focus.emit("Modo estándar activado.")
                
    def _load_actual_theme(self):
            """Carga el tema actual"""
            """Loads the actual theme"""
            file = "contrast_theme.qss" if self.high_contrast_mode else "dark_theme.qss"
            qss_dir = os.path.join(self.styles_dir, file)
            try:
                with open(qss_dir, "r", encoding="utf-8") as f:
                    QApplication.instance().setStyleSheet(f.read())
            except Exception as e:
                print(f"Aviso: No se pudo cargar el archivo CSS {file}: {e}")