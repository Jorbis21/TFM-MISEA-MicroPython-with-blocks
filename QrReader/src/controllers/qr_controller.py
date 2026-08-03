import threading
from models.qr_manager import QRManager

class QRController:
    def __init__(self, json_manager, workspace_dir):
        self.json_manager = json_manager
        self.workspace_dir = workspace_dir

    '''Obtiene todos los simbolos del json para poderlos seleccionar en la pestaña de QR'''
    def obtener_simbolos(self):
        return sorted(self.json_manager.construir_tabla_simbolos().keys())

    '''Genera el pdf con los elementos seleccionados'''
    def generar_pdf(self, elementos, tamano_mm, callback_estado):
        def _tarea():
            try:
                ruta_pdf = QRManager.generar_pdf_impresion(elementos, tamano_mm, self.workspace_dir)
                callback_estado(f"¡Éxito! PDF guardado en: {ruta_pdf}")
            except Exception as e:
                callback_estado(f"Error al generar PDF: {e}")
                
        callback_estado("Generando imágenes y PDF...")
        threading.Thread(target=_tarea, daemon=True).start()