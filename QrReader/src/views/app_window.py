import os

from PyQt6.QtGui import QShortcut, QKeySequence, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QPushButton, QWidget, QHBoxLayout, QMessageBox, QDialog

from views.tab_camara import TabCamara
from views.tab_json import TabJSON
from views.tab_qrs import TabQRs
from utils.constants import VoiceCommand
from utils.strings import t
from utils.language import get_language, set_language

class AppCamara(QMainWindow):
    """Ventana principal: monta las tres pestañas (cámara, generador de QRs, editor de diccionario), gestiona el tema de contraste, el idioma, los atajos de teclado y la navegación accesible por foco"""
    """Main window: assembles the three tabs (camera, QR generator, dictionary editor), manages the contrast theme, the language, keyboard shortcuts and accessible focus navigation"""

    spacebar_pressed = pyqtSignal()
    spacebar_released = pyqtSignal()
    changed_focus = pyqtSignal(str)
    window_closed = pyqtSignal()

    def __init__(self, workspace_dir, assets_dir, camera_ctrl, program_builder, audio_service, json_ctrl, qr_ctrl):
        """Construye las tres pestañas y sus controladores asociados, carga el tema guardado, configura los atajos de teclado y deja la ventana lista para mostrarse"""
        """Builds the three tabs and their associated controllers, loads the saved theme, sets up the keyboard shortcuts, and leaves the window ready to be shown"""
        super().__init__()
        
        self.setWindowTitle(t("window_title"))
        self.setWindowIcon(QIcon(os.path.join(assets_dir, "icons", "once.png")))
        self.resize(1280, 800)

        self.tabs = QTabWidget()
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCentralWidget(self.tabs)

        self.styles_dir = os.path.abspath(os.path.join(assets_dir, '..', 'styles'))
        self.high_contrast_mode = True
        
        self.theme_contrast = QShortcut(QKeySequence("Ctrl+T"), self)
        self.theme_contrast.activated.connect(self.change_contrast)

        self.language_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self.language_shortcut.activated.connect(self.change_language)

        self.camera_view = TabCamara(workspace_dir, assets_dir, camera_ctrl, program_builder, audio_service)
        
        self.qr_view = TabQRs(qr_ctrl)
        self.json_view = TabJSON(json_ctrl, assets_dir)

        self.language_btn = QPushButton(t("btn_change_language"))
        self.language_btn.setObjectName("btn_idioma")
        self.language_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.language_btn.clicked.connect(self.change_language)

        self.contrast_btn = QPushButton(t("btn_contrast_mode"))
        self.contrast_btn.setObjectName("btn_contraste")
        self.contrast_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.contrast_btn.clicked.connect(self.change_contrast)

        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(6)
        corner_layout.addWidget(self.language_btn)
        corner_layout.addWidget(self.contrast_btn)

        self.tabs.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

        self.tabs.addTab(self.camera_view, t("tab_camera"))
        self.tabs.addTab(self.qr_view, t("tab_qrs"))
        self.tabs.addTab(self.json_view, t("tab_json"))
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

    def change_language(self):
        """Abre el selector de idioma para cambiarlo en cualquier momento; avisa de que hace falta reiniciar para aplicarlo. No disponible en modo contraste (igual que las pestañas de gestión)"""
        """Opens the language picker to change it at any time; warns that a restart is needed to apply it. Not available in contrast mode (same as the management tabs)"""
        if self.high_contrast_mode:
            return
        from views.language_dialog import LanguageDialog
        dialog = LanguageDialog(allow_cancel=True)
        dialog.setWindowIcon(self.windowIcon())
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen_language:
            if dialog.chosen_language != get_language():
                set_language(dialog.chosen_language)
                QMessageBox.information(
                    self,
                    "Idioma / Language",
                    "El cambio de idioma se aplicará al reiniciar la aplicación.\n"
                    "The language change will apply when you restart the app."
                )

    def freeze_ui(self, freeze):
        """Congela la interfaz"""
        """Freeze the interface"""
        self.tabs.setEnabled(not freeze)
        if freeze: 
            self.camera_view.status_label.setText(t("status_ui_frozen"))
        else: 
            self.camera_view.status_label.setText(t("status_camera_active"))

    def dispatch(self, action):
        """Ejecuta en la vista de camara la accion que corresponde al comando recibido (voz o atajo)"""
        """Runs the camera view action that corresponds to the received command (voice or shortcut)"""
        actions = {
            VoiceCommand.CAPTURE: self.camera_view.action_capture,
            VoiceCommand.SEND: self.camera_view.action_send,
            VoiceCommand.EXPLAIN: self.camera_view.action_ia_explain,
            VoiceCommand.READ: self.camera_view.action_read_qrs,
            VoiceCommand.CHANGE_TTS: self.camera_view.action_change_tts,
            VoiceCommand.REVIEW: self.camera_view.action_var_review,
        }
        func = actions.get(action)
        if func:
            func()

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

        shortcuts = [
            (("A", "Ñ"), t("shortcut_capture"), self.camera_view.action_capture),
            (("S", "L"), t("shortcut_send"), self.camera_view.action_send),
            (("D", "K"), t("shortcut_explain"), self.camera_view.action_ia_explain),
            (("F", "J"), t("shortcut_read"), self.camera_view.action_read_qrs),
            (("G", "H"), t("shortcut_tts"), self.camera_view.action_change_tts),
            (("V", "N"), t("shortcut_review"), self.camera_view.action_var_review),
        ]

        for keys, label, func in shortcuts:
            for key in keys:
                QShortcut(QKeySequence(key), self).activated.connect(
                    lambda k=key.lower(), l=label, f=func: self.camera_view.process_chortcut(k, l, f)
                )

    def _on_focus_changed(self, old_widget, new_widget):
        """Cambia el foco del boton seleccionado y omite algunos"""
        """Change the focus of the selected button and omit some"""
        if not old_widget or not new_widget: return
        if self.tabs.currentIndex() != 0: return

        if isinstance(new_widget, QPushButton):
            name_obj = new_widget.objectName()
            if name_obj in ["btn_contraste", "btn_idioma", "combo_cameras", "edit_btn"]: return
                
            text = new_widget.text().strip()
            if name_obj == "overlay_btn":
                if new_widget == self.camera_view.rotate_btn: text = t("focus_rotate_camera")
                elif new_widget == self.camera_view.shutdown_btn: text = t("focus_shutdown_camera")
            
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
            self.language_btn.setVisible(False)
            self.contrast_btn.setText(t("btn_standard_mode"))
            if not silent: 
                self.changed_focus.emit(t("focus_high_contrast_on"))
        else:
            if self.tabs.count() == 1:
                self.tabs.addTab(self.qr_view, t("tab_qrs"))
                self.tabs.addTab(self.json_view, t("tab_json"))
            self.language_btn.setVisible(True)
            self.contrast_btn.setText(t("btn_contrast_mode"))
            if not silent: 
                self.changed_focus.emit(t("focus_standard_on"))
                
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