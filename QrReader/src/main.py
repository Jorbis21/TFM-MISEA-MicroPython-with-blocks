import os, sys

# Silencia los avisos de bajo nivel de OpenCV (p. ej. los de VIDEOIO/DSHOW al
# sondear índices de cámara que no existen); solo se verán errores reales.
# Tiene que fijarse ANTES de que cv2 se importe por primera vez en cualquier sitio.
# Silences OpenCV's low-level warnings (e.g. the VIDEOIO/DSHOW ones when
# probing camera indices that don't exist); only real errors will show.
# Must be set BEFORE cv2 gets imported anywhere for the first time.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

# En Windows, si se lanza con python.exe, la barra de tareas agrupa por el
# "Application User Model ID" del proceso y por defecto usa el de python.exe
# -> aparece el icono de Python en vez del de la app. Fijar uno propio (antes
# de crear la QApplication) hace que Windows use el icono de la ventana.
# On Windows, when launched with python.exe, the taskbar groups by the
# process's "Application User Model ID" and defaults to python.exe's own
# -> Python's icon shows up instead of the app's. Setting a custom one
# (before creating QApplication) makes Windows use the window's own icon.
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
    resource_dir = get_resource_dir()
    data_dir = get_data_dir()

    # load_dotenv() sin argumentos busca el .env a partir del directorio de
    # trabajo actual (find_dotenv()), no de donde esta el .exe - empaquetado
    # con PyInstaller eso deja de ser fiable, igual que paso con las rutas de
    # datos y de configuracion. Se le da la ruta explicita, junto al .exe.
    # load_dotenv() with no arguments searches for .env starting from the
    # current working directory (find_dotenv()), not from where the .exe is -
    # packaged with PyInstaller that stops being reliable, same as it did
    # with the data and config paths. Giving it the explicit path, next to
    # the .exe.
    # utf-8-sig en vez de utf-8: si el .env se guarda con el Bloc de notas
    # eligiendo "UTF-8", Windows le añade un BOM al principio del archivo, y
    # con encoding="utf-8" normal eso rompe la primera clave en silencio (se
    # lee como cadena vacia, sin ningun error visible). utf-8-sig quita el
    # BOM si esta, y no hace nada si no lo esta - funciona en los dos casos.
    # utf-8-sig instead of utf-8: if .env is saved with Notepad choosing
    # "UTF-8", Windows adds a BOM at the start of the file, and with plain
    # encoding="utf-8" that silently breaks the first key (it reads as an
    # empty string, no visible error). utf-8-sig strips the BOM if present,
    # and does nothing if it isn't - works either way.
    load_dotenv(os.path.join(data_dir, ".env"), encoding="utf-8-sig")
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    
    if not api_key:
        print("ADVERTENCIA: No se ha encontrado GEMINI_API_KEY en el archivo .env")

    workspace_dir = os.path.join(data_dir, 'workspace')
    settings_dir = os.path.join(data_dir, 'data', 'config')       # settings.json: se escribe, tiene que persistir
    blocks_dir = os.path.join(resource_dir, 'data', 'config')     # blocks_es/en.json: vienen de fabrica, solo lectura
    assets_dir = os.path.join(resource_dir, 'data', 'assets')     # iconos, estilos, cache de voz: solo lectura

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
        # Si cierran la ventana sin elegir, se queda en español (el valor
        # inicial por defecto) y no se guarda nada - se volvera a preguntar
        # la proxima vez.
        # If they close the window without choosing, it stays on Spanish
        # (the initial default) and nothing gets saved - it will ask again
        # next time.

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