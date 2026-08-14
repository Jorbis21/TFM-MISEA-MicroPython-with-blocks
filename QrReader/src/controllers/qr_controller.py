import threading
from models.qr_manager import QRManager
from utils.main_thread import run_on_main_thread
from utils.strings import t

class QRController:
    def __init__(self, json_manager, workspace_dir):
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