import os
from models.vision import VisionEngine
from models.translator import MicrobitCompiler
from models.ai_manager import AIManager
from models.serial_manager import SerialMonitor
from models.file_manager import FileManager
from models.json_manager import JsonManager

from controllers.camera_controller import CameraController
from controllers.json_controller import JsonController
from controllers.qr_controller import QRController

from views.app_window import AppCamara

class AppController:
    def __init__(self, workspace_dir, config_dir, assets_dir):
        self.vision = VisionEngine()
        self.json_manager = JsonManager(config_dir)
        self.json_ctrl = JsonController(self.json_manager)
        self.traductor = MicrobitCompiler(config_dir, self.json_ctrl)
        self.ai_manager = AIManager("AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w")
        self.serial_monitor = SerialMonitor()
        
        ruta_estado = os.path.join(workspace_dir, "outputs", "program_state.json")
        ruta_codigo = os.path.join(workspace_dir, "outputs", "MicroBit_Code.py")
        self.file_manager = FileManager(ruta_estado, ruta_codigo)

        self.serial_monitor.arrancar()

        self.camara_ctrl = CameraController(self.traductor, self.file_manager, ruta_codigo)
        self.camara_ctrl.cargar_estado()
        
        self.qr_ctrl = QRController(self.json_ctrl, workspace_dir)

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

    '''Muestra la ventana de la aplicación'''
    def iniciar(self):
        self.ventana.show()

    '''Apaga el sistema de IA local y el monitor serial'''
    def apagar_sistema(self):
        if self.ai_manager is not None:
            self.ai_manager.apagar_ollama()
        if self.serial_monitor is not None:
            self.serial_monitor.detener()