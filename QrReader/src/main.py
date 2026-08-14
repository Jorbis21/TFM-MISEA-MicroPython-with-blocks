import os, sys
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
if os.name == 'nt':
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ONCE.MicroPythonPorBloques.QrReader.1")
    except Exception as e:
        print(f"Aviso: no se pudo fijar el AppUserModelID: {e}")

from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QIcon
from dotenv import load_dotenv

from utils.main_thread import init_main_thread_dispatcher
from utils.language import init_language, has_saved_language, set_language
from utils.app_paths import get_resource_dir, get_data_dir
from views.language_dialog import LanguageDialog

from services.audio import AudioService
from models.ai_manager import AIManager
from models.serial_manager import SerialMonitor
from models.json_manager import JsonManager
from models.vision import VisionEngine
from models.translator import MicrobitCompiler
from models.voice_control import VoiceCommandManager
from models.code_manager import CodeManager
from controllers.app_controller import AppController


def main():
    """Punto de entrada de la aplicación: calcula las rutas base, elige el idioma, construye todos los modelos y servicios, y arranca la interfaz"""
    """Application entry point: computes the base paths, chooses the language, builds all the models and services, and starts the interface"""
    resource_dir = get_resource_dir()
    data_dir = get_data_dir()

    load_dotenv(os.path.join(data_dir, ".env"), encoding="utf-8-sig")
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    
    if not api_key:
        print("ADVERTENCIA: No se ha encontrado GEMINI_API_KEY en el archivo .env")

    workspace_dir = os.path.join(data_dir, 'workspace')
    settings_dir = os.path.join(data_dir, 'data', 'config')
    blocks_dir = os.path.join(resource_dir, 'data', 'config')
    assets_dir = os.path.join(resource_dir, 'data', 'assets')

    os.makedirs(os.path.join(workspace_dir, 'inputs'), exist_ok=True)
    os.makedirs(os.path.join(workspace_dir, 'outputs'), exist_ok=True)

    first_run = not has_saved_language(settings_dir)
    init_language(settings_dir)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(assets_dir, "icons", "once.png")))

    if first_run:
        dialog = LanguageDialog()
        dialog.setWindowIcon(app.windowIcon())
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen_language:
            set_language(dialog.chosen_language)

    init_main_thread_dispatcher()

    audio_service = AudioService(assets_dir)
    audio_service.start()

    voice_manager = VoiceCommandManager(None, workspace_dir, audio_service)
    vision_engine = VisionEngine()
    json_manager = JsonManager(blocks_dir)
    traducer = MicrobitCompiler(blocks_dir, json_manager)
    
    ai_manager = AIManager(api_key, audio_service) 
    serial_monitor = SerialMonitor(audio_service)
    serial_monitor.start()

    state_dir = os.path.join(workspace_dir, "outputs", "program_state.json")
    code_dir = os.path.join(workspace_dir, "outputs", "MicroBit_Code.py")
    code_manager = CodeManager(state_dir, code_dir)

    main_controller = AppController(
        workspace_dir=workspace_dir,
        assets_dir=assets_dir,
        code_dir=code_dir,
        audio_service=audio_service,
        vision=vision_engine,
        json_manager=json_manager,
        traducer=traducer,
        ai_manager=ai_manager,
        serial_monitor=serial_monitor,
        voice_manager=voice_manager,
        code_manager=code_manager,
    )
    
    main_controller.start()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()