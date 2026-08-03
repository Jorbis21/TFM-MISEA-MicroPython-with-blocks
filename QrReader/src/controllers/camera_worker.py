import cv2, os, time
from PyQt6.QtCore import QThread, pyqtSignal

class CameraWorker(QThread):
    # Señal que transporta el frame BGR, el RGB para PyQt y los textos detectados
    nuevo_frame = pyqtSignal(object, object, list) 

    def __init__(self, vision_engine, parent=None):
        super().__init__(parent)
        self.vision = vision_engine
        self.corriendo = False
        self.rotar = False
        self.camara_activa = False

    '''Detecta las cámaras en el equipo para poder seleccionarlas'''
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

    '''Enciende la cámara y arranca el hilo'''
    def iniciar_hardware(self, cam_idx):
        self.vision.iniciar_camara(cam_idx)
        self.camara_activa = True
        self.corriendo = True
        self.start()

    '''Apaga la cámara temporalmente'''
    def pausar_hardware(self):
        self.stop()
        self.vision.liberar_camara()
        self.camara_activa = False

    '''Apaga la cámara y libera todos los recursos'''
    def liberar_todo(self):
        self.stop()
        self.vision.free()
        self.camara_activa = False

    '''Bucle principal del hilo'''
    def run(self):
        ultimo_procesamiento = time.time()
        
        while self.corriendo and self.camara_activa:
            # 1. Tarea ligera: Leer el frame de la webcam y dibujarle los cuadrados (30 FPS)
            frame_bgr, frame_rgb, textos = self.vision.obtener_frame_marcado(self.rotar)
            
            if frame_rgb is not None:
                self.nuevo_frame.emit(frame_bgr, frame_rgb, textos)
            
            # 2. Tarea pesada: Procesar QRs solo cada 0.15 segundos para no saturar la CPU
            tiempo_actual = time.time()
            if tiempo_actual - ultimo_procesamiento > 0.15:
                self.vision.actualizar_procesamiento()
                ultimo_procesamiento = tiempo_actual
                
            time.sleep(0.015) 

    '''Pausa la ejecución del hilo de la cámara'''
    def stop(self):
        self.corriendo = False
        self.wait()