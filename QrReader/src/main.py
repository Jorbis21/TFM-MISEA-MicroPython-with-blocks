import os, sys
from PyQt6.QtWidgets import QApplication
from dotenv import load_dotenv

from services.audio import AudioService
from models.ai_manager import AIManager
from models.serial_manager import SerialMonitor
from models.json_manager import JsonManager
from models.vision import VisionEngine
from models.translator import MicrobitCompiler
from models.voice_control import VoiceCommandManager
from controllers.app_controller import AppController


def main():
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    
    if not api_key:
        print("ADVERTENCIA: No se ha encontrado GEMINI_API_KEY en el archivo .env")

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    workspace_dir = os.path.join(base_dir, 'workspace')
    config_dir = os.path.join(base_dir, 'data', 'config')
    assets_dir = os.path.join(base_dir, 'data', 'assets')

    os.makedirs(os.path.join(workspace_dir, 'inputs'), exist_ok=True)
    os.makedirs(os.path.join(workspace_dir, 'outputs'), exist_ok=True)

    app = QApplication(sys.argv)

    audio_service = AudioService()
    audio_service.iniciar()

    voice_manager = VoiceCommandManager(None, workspace_dir, audio_service)
    vision_engine = VisionEngine()
    json_manager = JsonManager(config_dir)
    traductor = MicrobitCompiler(config_dir, json_manager)
    
    ai_manager = AIManager(api_key, audio_service) 
    serial_monitor = SerialMonitor(audio_service)

    controlador_principal = AppController(
        workspace_dir, assets_dir, audio_service, vision_engine, 
        json_manager, traductor, ai_manager, serial_monitor, voice_manager
    )
    voice_manager.callback_bloqueo_ui = controlador_principal.ventana.bloquear_interfaz
    
    controlador_principal.iniciar()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()