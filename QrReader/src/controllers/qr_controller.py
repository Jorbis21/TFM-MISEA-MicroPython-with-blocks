import threading
from models.qr_manager import QRManager
from utils.main_thread import run_on_main_thread
from utils.strings import t

class QRController:
    """Intermediario entre la pestaña de generación de QRs y el modelo QRManager: da la lista de bloques disponibles y lanza la generación del PDF en segundo plano"""
    """Intermediary between the QR-generation tab and the QRManager model: gives the list of available blocks and launches the PDF generation in the background"""

    def __init__(self, json_manager, workspace_dir):
        """Guarda las referencias al modelo del diccionario y a la carpeta de trabajo donde se guardan las imágenes intermedias de cada QR"""
        """Stores the references to the dictionary model and the workspace folder where each QR's intermediate images are saved"""
        self.json_manager = json_manager
        self.workspace_dir = workspace_dir

    def get_symbols(self):
        """Obtiene todos los simbolos del json para poderlos seleccionar"""
        """Gets all the symbols from de json to be able to select"""
        return sorted(self.json_manager.build_symbols_table().keys())

    def generate_pdf(self, elems, size_mm, dest_dir, callback_state, on_finished=None):
        """Genera el pdf con los elementos seleccionados"""
        """Generates the pdf with the selected elems"""
        def _task():
            """Genera el PDF en el hilo en segundo plano y despacha el resultado (éxito o error) al hilo principal"""
            """Generates the PDF on the background thread and dispatches the result (success or error) to the main thread"""
            try:
                pdf_dir = QRManager.generate_pdf(elems, size_mm, dest_dir, self.workspace_dir)
                run_on_main_thread(callback_state, t("pdf_success", path=pdf_dir))
            except Exception as e:
                run_on_main_thread(callback_state, t("pdf_error", error=e))
            finally:
                if on_finished:
                    run_on_main_thread(on_finished)
                
        callback_state(t("generating_pdf"))
        threading.Thread(target=_task, daemon=True).start()