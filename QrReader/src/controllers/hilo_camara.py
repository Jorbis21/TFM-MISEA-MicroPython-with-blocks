import cv2
import os
import time
from PyQt6.QtCore import QThread, pyqtSignal

class HiloCamara(QThread):
    # Señal que enviará los datos al hilo principal (GUI) de forma segura
    nuevo_frame = pyqtSignal(object, object, list) 

    def __init__(self, vision_engine, parent=None):
        super().__init__(parent)
        self.vision = vision_engine
        self.corriendo = False
        self.rotar = False
        self.camara_activa = False

    @staticmethod
    def detectar_camaras():
        """Detecta los índices de las cámaras conectadas al equipo."""
        camaras_activas = []
        for i in range(3):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
            if cap is not None and cap.isOpened():
                camaras_activas.append(i)
                cap.release()
        if not camaras_activas:
            camaras_activas = [0]
        return camaras_activas

    def iniciar_hardware(self, cam_idx):
        """Inicia el hardware de la cámara y arranca el hilo."""
        self.vision.iniciar_camara(cam_idx)
        self.camara_activa = True
        self.corriendo = True
        self.start()

    def pausar_hardware(self):
        """Detiene el hilo y libera el hardware de la cámara."""
        self.stop()
        self.vision.liberar_camara()
        self.camara_activa = False

    def liberar_todo(self):
        """Libera los recursos completos del motor de visión (para el cierre del programa)."""
        self.stop()
        self.vision.free()
        self.camara_activa = False

    def run(self):
        """Bucle principal de procesamiento de OpenCV."""
        while self.corriendo and self.camara_activa:
            frame_bgr, frame_rgb, textos = self.vision.markElems(self.rotar)
            if frame_rgb is not None:
                self.nuevo_frame.emit(frame_bgr, frame_rgb, textos)
            time.sleep(0.015) 

    def stop(self):
        """Detiene la ejecución del hilo."""
        self.corriendo = False
        self.wait()