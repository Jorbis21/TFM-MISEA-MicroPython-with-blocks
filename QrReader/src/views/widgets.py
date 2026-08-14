from PyQt6.QtWidgets import QLineEdit


class AutoCleanSearch(QLineEdit):
    """Campo de busqueda que se vacia al primer click, para no tener que borrar el texto anterior a mano"""
    """Search field that clears itself on the first click, so there's no need to manually erase the previous text"""
    def mousePressEvent(self, event):
        self.clear()
        super().mousePressEvent(event)