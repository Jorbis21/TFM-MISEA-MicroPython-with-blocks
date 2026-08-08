import time
from PyQt6.QtCore import QTimer

from controllers.camera_controller import CameraController
from controllers.json_controller import JsonController
from controllers.qr_controller import QRController
from views.app_window import AppCamara

from models.voice_control import InteractionEvent
from utils.constants import EventType, VoiceCommand

class AppController:

    def __init__(self, workspace_dir, assets_dir, code_dir, audio_service, vision, json_manager, traducer, ai_manager, serial_monitor, voice_manager, file_manager):
        self.audio_service = audio_service
        self.ai_manager = ai_manager
        self.serial_monitor = serial_monitor
        self.voice_manager = voice_manager

        self.window = AppCamara(
            workspace_dir, 
            assets_dir, 
            CameraController(workspace_dir, code_dir, traducer, file_manager, 
            audio_service, vision, ai_manager,  voice_manager), 
            JsonController(json_manager, traducer), 
            QRController(json_manager, workspace_dir)
        )

        self.window.spacebar_pressed.connect(self.on_spacebar_pressed)
        self.window.spacebar_released.connect(self.on_spacebar_released)
        self.window.shortcut_command.connect(self.on_shortcut_command)
        self.window.changed_focus.connect(self.on_changed_focus)
        self.window.window_closed.connect(self.sys_shutdown)
        
        self.voice_manager.callback_command = self.on_voice_command
        self.voice_manager.callback_freeze_ui = self.window.freeze_ui

        self.pressed_time = 0
        self.space_clicks = 0
        self.space_timer = QTimer()
        self.space_timer.setSingleShot(True)
        self.space_timer.timeout.connect(self._process_spacebar_clicks)

    def start(self):
        """Muestra la ventana y avisa de que el sistema esta listo"""
        """Shows the main window and warns that system is ready"""
        self.window.show()
        self.audio_service.read_text("Sistema listo. La cámara está en modo horizontal.")

    def sys_shutdown(self):
        """Se apaga todos los sistemas antes de salir de la aplicacion"""
        """Shutdowns all the systems before closing the app"""
        self.voice_manager.stop()
        self.ai_manager.shutdown_ollama()
        self.serial_monitor.stop()
        self.audio_service.stop()

    """Control de teclado"""
    """Keyboard control"""

    def on_changed_focus(self, text):
        """Lee el texto de los botones al pasar por ellos"""
        """Reads buttons text when focusing on them"""
        self.audio_service.read_text_interrupting(text)

    def on_spacebar_pressed(self):
        """Gestiona el inicio del sistema de grabacion"""
        """Manage the start of the recording system"""
        self.pressed_time = time.time()
        self.voice_manager.start_dictation_record()

    def on_spacebar_released(self):
        """Gestiona la grabacion de voz al mantener presionado el espacio"""
        """Manage the voice recording when holding the spacebar"""
        duracion = time.time() - self.pressed_time
        
        if duracion < 0.4:
            self.voice_manager.discard_dictation_record()
            self.space_clicks += 1
            self.space_timer.start(400) 
        else:
            self.space_clicks = 0
            self.space_timer.stop()
            self.voice_manager.stop_dictation_and_process()

    def _process_spacebar_clicks(self):
        """Gestiona segun el numero de pulsaciones que evento enviar"""
        """Manage the event depending on the number of taps"""
        taps = self.space_clicks
        self.space_clicks = 0
        
        if taps == 1:
            self.voice_manager.inject_event(InteractionEvent(type=EventType.TAP, afirmative=False))
        elif taps == 2:
            self.voice_manager.inject_event(InteractionEvent(type=EventType.TAP, afirmative=True))
        elif taps >= 3:
            self.voice_manager.inject_event(InteractionEvent(type=EventType.SKIP))

    """Comandos por voz"""
    """Voice commands"""

    def on_shortcut_command(self, action):
        """Ejecuta la accion recibida por atajo de teclado"""
        """Runs the action recieved by keyboard shortcut"""
        self._run_command(action)

    def on_voice_command(self, action):
        """Ejecuta la accion recibida por voz"""
        """Runs the action recieved by voice"""
        self._run_command(action)

    def _run_command(self, action):
        """Ejecuta la accion segun el commando recibido"""
        """Runs the action according to the recieved command"""
        if action == VoiceCommand.CAPTURE:
            self.window.camera_view.action_capture()
        elif action == VoiceCommand.SEND:
            self.window.camera_view.action_send()
        elif action == VoiceCommand.EXPLAIN:
            self.window.camera_view.action_ia_explain()
        elif action == VoiceCommand.READ:
            self.window.camera_view.action_read_qrs()
        elif action == VoiceCommand.CHANGE_TTS:
            self.window.camera_view.action_change_tts()
        elif action == VoiceCommand.REVIEW:
            self.window.camera_view.action_var_review()