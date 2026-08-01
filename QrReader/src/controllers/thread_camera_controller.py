import cv2, os, time
from PyQt6.QtCore import QThread, pyqtSignal

class ThreadCameraController(QThread):
    nuevo_frame = pyqtSignal(object, object, list) 

    def __init__(self, vision_engine, parent=None):
        super().__init__(parent)
        self.vision = vision_engine
        self.corriendo = False
        self.rotar = False
        self.camara_activa = False

    '''Detecta las camaras detectadas en el equipor para poder seleccionarlas'''
    @staticmethod
    def detectar_camaras():
        camaras_activas = []
        for i in range(3):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
            if cap is not None and cap.isOpened():
                camaras_activas.append(i)
                cap.release()
        if not camaras_activas:
            camaras_activas = [0]
        return camaras_activas

    '''Enciende la camara para hacer uso de ella'''
    def iniciar_hardware(self, cam_idx):
        self.vision.iniciar_camara(cam_idx)
        self.camara_activa = True
        self.corriendo = True
        self.start()

    '''Apaga la camara'''
    def pausar_hardware(self):
        self.stop()
        self.vision.liberar_camara()
        self.camara_activa = False

    '''Apaga la camara y el hilo'''
    def liberar_todo(self):
        self.stop()
        self.vision.free()
        self.camara_activa = False

    '''Corre el procesamiento de vision artificial por OpenCV'''
    def run(self):
        while self.corriendo and self.camara_activa:
            frame_bgr, frame_rgb, textos = self.vision.markElems(self.rotar)
            if frame_rgb is not None:
                self.nuevo_frame.emit(frame_bgr, frame_rgb, textos)
            time.sleep(0.015) 

    '''Pausa la ejecucion del hilo de la camara'''
    def stop(self):
        self.corriendo = False
        self.wait()