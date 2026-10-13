from controllers.camera_worker import CameraWorker
from utils.camera_prefs import get_saved_camera_name, save_camera_name


class CameraController:

    """
        Controla exclusivamente el hardware de la camara: encenderla, pausarla,
        liberarla, rotarla y detectar que camaras hay disponibles. Todo lo
        relacionado con construir el programa vive en ProgramBuilder.
    """
    """
        Controls exclusively the camera hardware: turning it on, pausing it,
        freeing it, rotating it and detecting which cameras are available.
        Everything related to building the program lives in ProgramBuilder.
    """

    def __init__(self, vision, audio_service):
        """Guarda las referencias al modelo de visión y al servicio de audio, y crea el hilo de cámara asociado a ese modelo"""
        """Stores the references to the vision model and the audio service, and creates the camera thread associated with that model"""
        self.vision = vision
        self.audio_service = audio_service
        self.camera_thr = CameraWorker(self.vision)

    def start_camera_hardware(self, idx, rotate=False):
        """Inicia el hardware de la camara"""
        """Starts camera hardware"""
        self.camera_thr.rotate = rotate
        self.camera_thr.start_hardware(idx)

    def pause_camera_hardware(self):
        """Pausa el hardware de la camara"""
        """Pauses camera hardware"""
        self.camera_thr.pause_hardware()

    def set_rotation_camera(self, rotate):
        """Modifica la rotacion de la camara"""
        """Changes the camera rotation"""
        self.camera_thr.rotate = rotate
        if rotate:
            self.audio_service.read_text_interrupting("Cámara en modo vertical.")
        else:
            self.audio_service.read_text_interrupting("Cámara en modo horizontal.")

    def free_camera_resources(self):
        """Libera los recursos de la camara"""
        """Frees all the camera resources"""
        self.camera_thr.free_all()

    def detect_cameras(self):
        """Detecta las camaras conectadas al ordenador: lista de (indice, nombre)"""
        """Detects the connected cameras to the computer: list of (index, name)"""
        return self.camera_thr.detect_cameras()

    def choose_preferred_camera(self, cameras):
        """Devuelve la posicion de la camara con la que arrancar (la ultima elegida, o la SVPRO, o una externa)"""
        """Returns the position of the camera to start with (the last chosen one, or the SVPRO, or an external one)"""
        return self.camera_thr.choose_preferred(cameras, get_saved_camera_name())

    def remember_camera(self, name):
        """Recuerda la camara elegida por el usuario para la proxima vez"""
        """Remembers the camera chosen by the user for next time"""
        save_camera_name(name)