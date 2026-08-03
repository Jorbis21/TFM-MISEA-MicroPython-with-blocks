import os, sys
from PyQt6.QtWidgets import QApplication

# Importa tus servicios y controladores
from services.audio import AudioService
from models.ai_manager import AIManager
from models.serial_manager import SerialMonitor
from models.json_manager import JsonManager
from models.vision import VisionEngine
from models.translator import MicrobitCompiler
from models.voice_control import VoiceCommandManager
from controllers.app_controller import AppController
from controllers.camera_controller import CameraController
from controllers.json_controller import JsonController
from controllers.qr_controller import QRController

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    workspace_dir = os.path.join(base_dir, 'workspace')
    config_dir = os.path.join(base_dir, 'data', 'config')
    assets_dir = os.path.join(base_dir, 'data', 'assets')

    os.makedirs(os.path.join(workspace_dir, 'inputs'), exist_ok=True)
    os.makedirs(os.path.join(workspace_dir, 'outputs'), exist_ok=True)

    app = QApplication(sys.argv)

    # 1. INSTANCIAR SERVICIOS BASE
    audio_service = AudioService()
    audio_service.iniciar() # Arrancamos el hilo de voz de forma controlada

    # 2. INSTANCIAR MODELOS Y MOTORES (Inyectando el audio donde haga falta)
    voice_manager = VoiceCommandManager(None, workspace_dir, audio_service)
    vision_engine = VisionEngine()
    json_manager = JsonManager(config_dir)
    traductor = MicrobitCompiler(config_dir, json_manager)
    
    # Fíjate cómo ahora le pasamos el audio por parámetro
    ai_manager = AIManager("AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w", audio_service) 
    serial_monitor = SerialMonitor(audio_service)

    # 3. INSTANCIAR EL CONTROLADOR PRINCIPAL
    # Le pasamos todo ya fabricado para que no tenga que usar 'new'
    controlador_principal = AppController(
        workspace_dir, assets_dir, audio_service, vision_engine, 
        json_manager, traductor, ai_manager, serial_monitor, voice_manager
    )
    voice_manager.callback_bloqueo_ui = controlador_principal.ventana.bloquear_interfaz
    
    controlador_principal.iniciar()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()