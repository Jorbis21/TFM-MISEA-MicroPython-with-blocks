import threading
from models.qr_manager import QRManager

class QRController:
    """Orquesta la pestaña de generación de PDFs."""
    def __init__(self, traductor, workspace_dir):
        self.traductor = traductor
        self.workspace_dir = workspace_dir

    def obtener_simbolos(self):
        return sorted(self.traductor.tabla_simbolos.keys())

    def generar_pdf(self, elementos, tamano_mm, callback_estado):
        def _tarea():
            try:
                ruta_pdf = QRManager.generar_pdf_impresion(elementos, tamano_mm, self.workspace_dir)
                callback_estado(f"¡Éxito! PDF guardado en: {ruta_pdf}")
            except Exception as e:
                callback_estado(f"Error al generar PDF: {e}")
                
        callback_estado("Generando imágenes y PDF...")
        threading.Thread(target=_tarea, daemon=True).start()