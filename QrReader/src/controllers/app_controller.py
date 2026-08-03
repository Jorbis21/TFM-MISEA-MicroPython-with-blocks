import os
import time
from PyQt6.QtCore import QTimer

from models.file_manager import FileManager
from controllers.camera_controller import CameraController
from controllers.json_controller import JsonController
from controllers.qr_controller import QRController
from views.app_window import AppCamara

from models.voice_control import EventoInteraccion
from utils.constants import TipoEvento, ComandoVoz


class AppController:
    def __init__(self, workspace_dir, assets_dir, audio_service, vision, json_manager, traductor, ai_manager, serial_monitor, voice_manager):
        # 1. Guardamos las referencias inyectadas
        self.audio_service = audio_service
        self.vision = vision
        self.json_manager = json_manager
        self.traductor = traductor
        self.ai_manager = ai_manager
        self.serial_monitor = serial_monitor
        self.voice_manager = voice_manager
        
        # 2. Inicialización de archivos
        ruta_estado = os.path.join(workspace_dir, "outputs", "program_state.json")
        ruta_codigo = os.path.join(workspace_dir, "outputs", "MicroBit_Code.py")
        self.file_manager = FileManager(ruta_estado, ruta_codigo)

        # 3. Arrancamos los demonios que vienen inyectados
        self.serial_monitor.arrancar()

        # 4. Instanciamos los sub-controladores
        self.camara_ctrl = CameraController(
            self.traductor, self.file_manager, self.audio_service, 
            ruta_codigo, self.vision, self.ai_manager, workspace_dir
        )
        self.camara_ctrl.cargar_estado()
        # Le pasamos el voice_manager al controlador de la cámara
        self.camara_ctrl.set_voice_manager(self.voice_manager)
        
        self.json_ctrl = JsonController(self.json_manager, self.traductor)
        self.qr_ctrl = QRController(self.json_manager, workspace_dir)

        # 5. Instanciamos la Vista
        self.ventana = AppCamara(
            workspace_dir, 
            assets_dir, 
            self.camara_ctrl, 
            self.json_ctrl, 
            self.qr_ctrl
        )

        # 6. Conectamos señales de la vista a este controlador
        self.ventana.espacio_presionado.connect(self.on_espacio_presionado)
        self.ventana.espacio_soltado.connect(self.on_espacio_soltado)
        self.ventana.comando_atajo.connect(self.on_comando_atajo)
        self.ventana.foco_cambiado.connect(self.on_foco_cambiado)
        
        # Enlazamos el motor de voz con el controlador
        self.voice_manager.callback_comando = self.on_comando_voz
        self.voice_manager.callback_bloqueo_ui = self.ventana.bloquear_interfaz

        # Lógica de tiempos para el espacio
        self.tiempo_presion = 0
        self.clics_espacio = 0
        self.timer_espacio = QTimer()
        self.timer_espacio.setSingleShot(True)
        self.timer_espacio.timeout.connect(self._procesar_clics_espacio)

    def iniciar(self):
        self.ventana.show()

    def apagar_sistema(self):
        if self.ai_manager is not None:
            self.ai_manager.apagar_ollama()
        if self.serial_monitor is not None:
            self.serial_monitor.detener()
        if self.audio_service is not None:
            self.audio_service.detener()

    # --- LÓGICA DE CONTROL DEL TECLADO Y AUDIO ---

    def on_foco_cambiado(self, texto):
        self.audio_service.leer_texto_interrumpiendo(texto)

    def on_espacio_presionado(self):
        self.tiempo_presion = time.time()
        self.voice_manager.start_dictation_record()

    def on_espacio_soltado(self):
        duracion = time.time() - self.tiempo_presion
        
        if duracion < 0.4:
            self.voice_manager.discard_dictation_record()
            self.clics_espacio += 1
            self.timer_espacio.start(400) 
        else:
            self.clics_espacio = 0
            self.timer_espacio.stop()
            self.voice_manager.stop_dictation_and_process()

    def _procesar_clics_espacio(self):
        taps = self.clics_espacio
        self.clics_espacio = 0
        
        if taps == 1:
            self.voice_manager.inyectar_evento(EventoInteraccion(tipo=TipoEvento.TOQUE_FISICO, es_afirmativo=False))
        elif taps == 2:
            self.voice_manager.inyectar_evento(EventoInteraccion(tipo=TipoEvento.TOQUE_FISICO, es_afirmativo=True))
        elif taps >= 3:
            self.voice_manager.inyectar_evento(EventoInteraccion(tipo=TipoEvento.OMITIR))

    # --- ENRUTAMIENTO DE COMANDOS ---

    def on_comando_atajo(self, accion):
        self._ejecutar_accion(accion)

    def on_comando_voz(self, comando):
        # Mapeamos los comandos de voz de Whisper a los strings semánticos
        mapeo = {
            ComandoVoz.CAPTURAR: "capturar",
            ComandoVoz.ENVIAR: "enviar",
            ComandoVoz.EXPLICAR: "explicar",
            ComandoVoz.LEER: "leer",
            ComandoVoz.CAMBIAR_TTS: "cambiar_tts",
            ComandoVoz.REPASAR: "repasar"
        }
        accion = mapeo.get(comando)
        if accion:
            self._ejecutar_accion(accion)

    def _ejecutar_accion(self, accion):
        # Dirigimos la acción requerida a la VISTA de la cámara (TabCamara)
        # porque es ahí donde están definidas 'accion_capturar', 'accion_enviar', etc.
        if accion == "capturar":
            self.ventana.vista_camara.accion_capturar()
        elif accion == "enviar":
            self.ventana.vista_camara.accion_enviar()
        elif accion == "explicar":
            self.ventana.vista_camara.accion_explicar_ia()
        elif accion == "leer":
            self.ventana.vista_camara.accion_leer_qrs_pantalla()
        elif accion == "cambiar_tts":
            self.ventana.vista_camara.accion_cambiar_tts()
        elif accion == "repasar":
            self.ventana.vista_camara.accion_repasar_variables()