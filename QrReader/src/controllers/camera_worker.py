import cv2, os, time
from PyQt6.QtCore import QThread, pyqtSignal

class CameraWorker(QThread):

    """Señal que envia los frames"""
    """Signal that sends the new frames"""
    new_frame = pyqtSignal(object, object, list) 

    def __init__(self, vision, parent=None):
        """Guarda la referencia al modelo de visión y deja el hilo en reposo, sin arrancar la cámara todavía"""
        """Stores the reference to the vision model and leaves the thread idle, without starting the camera yet"""
        super().__init__(parent)
        self.vision = vision
        self.running = False
        self.rotate = False
        self.active_camera = False

    @staticmethod
    def detect_cameras():
        """Detecta las camaras conectadas al ordenador"""
        """Detects the connected cameras to the computer"""
        active_cameras = []
        for i in range(3):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
            if cap is not None and cap.isOpened():
                active_cameras.append(i)
                cap.release()
        if not active_cameras:
            active_cameras = [0]
        return active_cameras

    def start_hardware(self, cam_idx):
        """Enciende la camara"""
        """Starts the camera"""
        self.vision.start_camera(cam_idx)
        self.active_camera = True
        self.running = True
        self.start()

    def pause_hardware(self):
        """Pausa la camara temporalmente"""
        """Pauses the camera"""
        self.stop()
        self.vision.free_camera()
        self.active_camera = False

    def free_all(self):
        """Apaga la camara y libera los recursos"""
        """Shutdowns the camera and free the resources"""
        self.stop()
        self.vision.free()
        self.active_camera = False

    def run(self):
        """Bucle principal del hilo de la camara"""
        """Main loop of the camera thread"""
        last_process = time.time()
        
        while self.running and self.active_camera:
            frame_bgr, frame_rgb, texts = self.vision.get_marked_frame(self.rotate)
            
            if frame_rgb is not None:
                self.new_frame.emit(frame_bgr, frame_rgb, texts)
            
            actual_time = time.time()
            if actual_time - last_process > 0.15:
                self.vision.update_process()
                last_process = actual_time
                
            time.sleep(0.015) 

    def stop(self):
        """Pausa la ejecucion del hilo"""
        """Pauses the ejecution of the thread"""
        self.running = False
        self.wait(1000)