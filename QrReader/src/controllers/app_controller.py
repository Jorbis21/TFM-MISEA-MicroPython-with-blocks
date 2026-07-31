import os
from models.vision import VisionEngine
from models.translator import MicrobitCompiler
from models.ai_manager import AIManager
from models.serial_manager import SerialMonitor
from models.file_manager import FileManager
from models.json_manager import JsonManager

from controllers.camara_controller import CamaraController
from controllers.json_controller import JsonController
from controllers.qr_controller import QRController

# Aquí importaremos la vista principal (todavía no modifiques app_window, lo haremos luego)
from views.app_window import AppCamara

class AppController:
    def __init__(self, workspace_dir, config_dir, assets_dir):
        # 1. Instanciar los Modelos Globales (Los Músculos y Datos)
        self.vision = VisionEngine()
        self.traductor = MicrobitCompiler(config_dir)
        self.ai_manager = AIManager("AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w")
        self.serial_monitor = SerialMonitor()
        self.json_manager = JsonManager(config_dir)
        
        ruta_estado = os.path.join(workspace_dir, "outputs", "program_state.json")
        ruta_codigo = os.path.join(workspace_dir, "outputs", "MicroBit_Code.py")
        self.file_manager = FileManager(ruta_estado, ruta_codigo)

        # 2. Iniciar demonios en segundo plano
        self.serial_monitor.arrancar()

        # 3. Instanciar los Controladores Secundarios
        self.camara_ctrl = CamaraController(self.traductor, self.file_manager, ruta_codigo)
        self.camara_ctrl.cargar_estado()
        self.json_ctrl = JsonController(self.json_manager, self.traductor)
        self.qr_ctrl = QRController(self.traductor, workspace_dir)

        # 4. Construir la Interfaz 
        # (Nota: En el siguiente paso limpiaremos app_window para que reciba estos controladores)
        self.ventana = AppCamara(
            workspace_dir, 
            assets_dir, 
            self.camara_ctrl, 
            self.json_ctrl, 
            self.qr_ctrl,
            self.vision,
            self.ai_manager,
            self.traductor,
            self
        )

    def iniciar(self):
        self.ventana.show()

    def apagar_sistema(self):
        """Libera todos los recursos de hardware y puertos al cerrar el programa."""
        if self.ai_manager is not None:
            self.ai_manager.apagar_ollama()
        if self.serial_monitor is not None:
            self.serial_monitor.detener()