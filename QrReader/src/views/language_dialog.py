from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import Qt

from utils.language import get_language_names, get_language


class LanguageDialog(QDialog):

    """
        Ventana para elegir el idioma: al primer arranque (allow_cancel=False,
        no se puede cerrar sin elegir), o en cualquier momento despues desde
        el boton "Idioma" (allow_cancel=True). No puede usar t("clave") para
        su propio texto -bilingue a proposito- porque el idioma que se este
        mostrando puede no ser el que la persona entiende en ese momento.
        El combo se rellena con utils.language.get_language_names(), asi que
        anadir un idioma nuevo ahi lo hace aparecer aqui solo.
    """
    """
        Window to choose the language: on first launch (allow_cancel=False,
        can't be closed without choosing), or at any later point from the
        "Language" button (allow_cancel=True). It can't use t("key") for its
        own text -bilingual on purpose- because the language currently shown
        might not be the one the person understands at that moment. The
        combo box is filled from utils.language.get_language_names(), so
        adding a new language there makes it show up here automatically.
    """

    def __init__(self, allow_cancel=False):
        super().__init__()
        self.setWindowTitle("Language")
        self.setFixedSize(340, 230)
        self.chosen_language = None

        if not allow_cancel:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        label = QLabel("Elige un idioma\nChoose a language")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 13pt;")
        layout.addWidget(label)

        self.combo = QComboBox()
        self.combo.setFixedHeight(36)
        self.combo.setStyleSheet("font-size: 12pt; padding: 4px 8px;")
        names = get_language_names()
        self._codes = list(names.keys())
        for code in self._codes:
            self.combo.addItem(names[code])
        current = get_language()
        if current in self._codes:
            self.combo.setCurrentIndex(self._codes.index(current))
        layout.addWidget(self.combo)

        # Alto y estilo fijados a mano en vez de heredar el tema de contraste
        # tal cual: en un dialogo pequeño, el padding que el tema aplica a un
        # QPushButton normal puede dejar menos alto del que ocupa el texto, y
        # se ve cortado por arriba y por abajo.
        # Height and style set explicitly instead of inheriting the contrast
        # theme as-is: in a small dialog, the padding the theme applies to a
        # plain QPushButton can leave less height than the text needs, and it
        # shows up clipped on top and bottom.
        button_style = "font-size: 12pt; padding: 4px;"

        btns_layout = QHBoxLayout()
        if allow_cancel:
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(42)
            cancel_btn.setStyleSheet(button_style)
            cancel_btn.clicked.connect(self.reject)
            btns_layout.addWidget(cancel_btn)

        accept_btn = QPushButton("OK")
        accept_btn.setFixedHeight(42)
        accept_btn.setStyleSheet(button_style)
        accept_btn.setDefault(True)
        accept_btn.clicked.connect(self._accept_choice)
        btns_layout.addWidget(accept_btn)
        layout.addLayout(btns_layout)

    def _accept_choice(self):
        """Guarda el idioma seleccionado en el combo y cierra la ventana"""
        """Saves the language selected in the combo box and closes the window"""
        self.chosen_language = self._codes[self.combo.currentIndex()]
        self.accept()