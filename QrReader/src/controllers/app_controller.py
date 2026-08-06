import time
from PyQt6.QtCore import QTimer

from controllers.camera_controller import CameraController
from controllers.json_controller import JsonController
from controllers.qr_controller import QRController
from views.app_window import AppCamara

from models.voice_control import EventoInteraccion
from utils.constants import TipoEvento, ComandoVoz

class AppController:

    def __init__(self, workspace_dir, assets_dir, code_dir, audio_service, vision, json_manager, traductor, ai_manager, serial_monitor, voice_manager, file_manager):
        self.audio_service = audio_service
        self.ai_manager = ai_manager
        self.serial_monitor = serial_monitor
        self.voice_manager = voice_manager

        self.window = AppCamara(
            workspace_dir, 
            assets_dir, 
            CameraController(
            traductor, file_manager, audio_service, 
            code_dir, vision, ai_manager, workspace_dir, voice_manager), 
            JsonController(json_manager, traductor), 
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
        self.window.show()
        self.audio_service.leer_texto("Sistema listo. La cámara está en modo horizontal.")

    def sys_shutdown(self):
        """Se apaga todos los sistemas antes de salir de la aplicacion"""
        self.voice_manager.detener()
        self.ai_manager.apagar_ollama()
        self.serial_monitor.detener()
        self.audio_service.detener()

    """Control de teclado"""

    def on_changed_focus(self, texto):
        """Lee el texto de los botones al pasar por ellos"""
        self.audio_service.leer_texto_interrumpiendo(texto)

    def on_spacebar_pressed(self):
        """Gestiona el inicio del sistema de grabacion"""
        self.pressed_time = time.time()
        self.voice_manager.start_dictation_record()

    def on_spacebar_released(self):
        """Gestiona la grabacion de voz al mantener presionado el espacio"""
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
        taps = self.space_clicks
        self.space_clicks = 0
        
        if taps == 1:
            self.voice_manager.inyectar_evento(EventoInteraccion(tipo=TipoEvento.TOQUE_FISICO, es_afirmativo=False))
        elif taps == 2:
            self.voice_manager.inyectar_evento(EventoInteraccion(tipo=TipoEvento.TOQUE_FISICO, es_afirmativo=True))
        elif taps >= 3:
            self.voice_manager.inyectar_evento(EventoInteraccion(tipo=TipoEvento.OMITIR))

    """Comandos por voz"""

    def on_shortcut_command(self, accion):
        """Ejecuta la accion recibida por atajo de teclado"""
        self._run_command(accion)

    def on_voice_command(self, accion):
        """Ejecuta la accion recibida por voz"""
        self._run_command(accion)

    def _run_command(self, accion):
        """Ejecuta la accion segun el commando recibido"""
        if accion == ComandoVoz.CAPTURAR:
            self.window.vista_camara.accion_capturar()
        elif accion == ComandoVoz.ENVIAR:
            self.window.vista_camara.accion_enviar()
        elif accion == ComandoVoz.EXPLICAR:
            self.window.vista_camara.accion_explicar_ia()
        elif accion == ComandoVoz.LEER:
            self.window.vista_camara.accion_leer_qrs_pantalla()
        elif accion == ComandoVoz.CAMBIAR_TTS:
            self.window.vista_camara.accion_cambiar_tts()
        elif accion == ComandoVoz.REPASAR:
            self.window.vista_camara.accion_repasar_variables()