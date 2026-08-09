import threading
from models.qr_manager import QRManager

class QRController:
    def __init__(self, json_manager, workspace_dir):
        self.json_manager = json_manager
        self.workspace_dir = workspace_dir

    def get_symbols(self):
        """Obtiene todos los simbolos del json para poderlos seleccionar"""
        """Gets all the symbols from de json to be able to select"""
        return sorted(self.json_manager.build_symbols_table().keys())

    def generate_pdf(self, elems, size_mm, dest_dir, callback_state):
        """Genera el pdf con los elementos seleccionados"""
        """Generates the pdf with the selected elems"""
        def _task():
            try:
                pdf_dir = QRManager.generate_pdf(elems, size_mm, dest_dir, self.workspace_dir)
                callback_state(f"¡Éxito! PDF guardado en: {pdf_dir}")
            except Exception as e:
                callback_state(f"Error al generar PDF: {e}")
                
        callback_state("Generando imágenes y PDF...")
        threading.Thread(target=_task, daemon=True).start()