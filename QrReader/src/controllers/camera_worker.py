import cv2, os, re, time
from PyQt6.QtCore import QThread, pyqtSignal


"""
    Palabras que identifican la camara de documentos preferida (SVPRO 12MP,
    sensor IMX362). Se comparan en minusculas contra el nombre que da el
    sistema operativo. Si tu camara aparece con otro nombre (mira la consola
    al arrancar: "[Camaras detectadas]"), añade aqui una parte de ese nombre.
"""
"""
    Words that identify the preferred document camera (SVPRO 12MP, IMX362
    sensor). They are compared in lowercase against the name the operating
    system reports. If your camera shows up with another name (check the
    console at startup: "[Camaras detectadas]"), add part of that name here.
"""
PREFERRED_CAMERA_KEYWORDS = ["svpro", "12mp", "imx362", "autofocus", "autofokus"]

"""Palabras que delatan una camara integrada del portatil (o de infrarrojos), que nunca es la buena"""
"""Words that give away a built-in laptop camera (or an infrared one), which is never the right one"""
BUILTIN_CAMERA_KEYWORDS = ["integrated", "integrada", "built-in", "facetime", "ir camera", "infrared", "virtual", "obs"]


class CameraWorker(QThread):

    """Señal que envia los frames"""
    """Signal that sends the new frames"""
    new_frame = pyqtSignal(object, object, list)

    def __init__(self, vision, parent=None):
        """Guarda la referencia al modelo de visión y deja el hilo en reposo, sin arrancar la cámara todavía"""
        """Stores the reference to the vision model and leaves the thread idle, without starting the camera yet"""
        super().__init__(parent)
        self.vision = vision
        self.rotate = False

        # Toda la apertura/cierre de la camara ocurre DENTRO de este hilo.
        # El hilo de la interfaz solo deja aqui la camara que quiere
        # (None = ninguna) y el hilo se encarga de abrirla o cerrarla. Asi
        # abrir una camara con DirectShow (que puede tardar segundos) nunca
        # congela la ventana ni deja eventos de teclado/raton en cola.
        # All opening/closing of the camera happens INSIDE this thread. The
        # UI thread only leaves here which camera it wants (None = none) and
        # the thread takes care of opening or closing it. This way opening a
        # camera with DirectShow (which can take seconds) never freezes the
        # window nor leaves keyboard/mouse events queued.
        self._requested_idx = None
        self._opened_idx = None
        self._quit = False

    # ------------------------------------------------------------------
    # Deteccion de camaras / Camera detection
    # ------------------------------------------------------------------

    @staticmethod
    def _get_device_names():
        """Devuelve los nombres de las camaras en el mismo orden que usa OpenCV, o None si el sistema no permite saberlo"""
        """Returns the camera names in the same order OpenCV uses, or None if the system doesn't allow finding out"""
        if os.name == 'nt':
            # pygrabber enumera los dispositivos DirectShow en el mismo orden
            # que cv2.VideoCapture(i, cv2.CAP_DSHOW)
            # pygrabber enumerates the DirectShow devices in the same order as
            # cv2.VideoCapture(i, cv2.CAP_DSHOW)
            try:
                from pygrabber.dshow_graph import FilterGraph
                return list(FilterGraph().get_input_devices())
            except Exception as e:
                print(f"Aviso: no se pudieron leer los nombres de las camaras (pip install pygrabber): {e}")
                return None

        sys_dir = "/sys/class/video4linux"
        if os.path.isdir(sys_dir):
            names = {}
            for dev in os.listdir(sys_dir):
                m = re.match(r"video(\d+)$", dev)
                if not m: continue
                # Cada camara USB crea dos nodos (video + metadatos); solo el
                # de indice 0 sirve para capturar
                # Each USB camera creates two nodes (video + metadata); only
                # the one with index 0 can capture
                try:
                    with open(os.path.join(sys_dir, dev, "index")) as f:
                        if f.read().strip() != "0": continue
                except OSError:
                    pass
                try:
                    with open(os.path.join(sys_dir, dev, "name")) as f:
                        names[int(m.group(1))] = f.read().strip()
                except OSError:
                    names[int(m.group(1))] = f"video{m.group(1)}"
            return names or None
        return None

    @staticmethod
    def detect_cameras():
        """Detecta las camaras conectadas. Devuelve una lista de (indice, nombre); el nombre es None si no se puede saber"""
        """Detects the connected cameras. Returns a list of (index, name); the name is None if it can't be known"""
        names = CameraWorker._get_device_names()

        if isinstance(names, list):
            cameras = [(i, n) for i, n in enumerate(names)]
        elif isinstance(names, dict):
            cameras = sorted(names.items())
        else:
            cameras = []
            for i in range(3):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
                if cap is not None and cap.isOpened():
                    cameras.append((i, None))
                    cap.release()

        if not cameras:
            cameras = [(0, None)]
        print("[Camaras detectadas]:", ", ".join(f"{i}: {n or 'sin nombre'}" for i, n in cameras))
        return cameras

    @staticmethod
    def choose_preferred(cameras, saved_name=None):
        """
            Elige la camara con la que arrancar, por orden de prioridad:
            1) la que el usuario eligio la ultima vez (por nombre),
            2) la que coincide con PREFERRED_CAMERA_KEYWORDS (la SVPRO),
            3) cualquier camara externa (no integrada del portatil),
            4) la primera.
            Devuelve la posicion dentro de la lista 'cameras'.
        """
        """
            Chooses the camera to start with, by priority:
            1) the one the user chose last time (by name),
            2) the one matching PREFERRED_CAMERA_KEYWORDS (the SVPRO),
            3) any external camera (not the laptop's built-in one),
            4) the first one.
            Returns the position inside the 'cameras' list.
        """
        lowered = [(pos, (name or "").lower()) for pos, (_, name) in enumerate(cameras)]

        if saved_name:
            for pos, name in lowered:
                if name and name == saved_name.lower():
                    return pos

        for pos, name in lowered:
            if any(k in name for k in PREFERRED_CAMERA_KEYWORDS):
                return pos

        if len(cameras) > 1:
            for pos, name in lowered:
                if name and not any(k in name for k in BUILTIN_CAMERA_KEYWORDS):
                    return pos
        return 0

    # ------------------------------------------------------------------
    # Control desde la interfaz (no bloqueante) / Control from the UI (non-blocking)
    # ------------------------------------------------------------------

    def start_hardware(self, cam_idx):
        """Pide encender (o cambiar a) la camara indicada; el hilo la abre en segundo plano"""
        """Requests turning on (or switching to) the given camera; the thread opens it in the background"""
        self._requested_idx = cam_idx
        self._quit = False
        if not self.isRunning():
            self.start()

    def pause_hardware(self):
        """Pide apagar la camara; el hilo la libera en segundo plano"""
        """Requests turning the camera off; the thread releases it in the background"""
        self._requested_idx = None

    def free_all(self):
        """Apaga la camara, termina el hilo y libera los recursos (al cerrar la aplicacion)"""
        """Shuts the camera down, ends the thread and frees the resources (when closing the app)"""
        self._requested_idx = None
        self._quit = True
        if self.isRunning() and not self.wait(5000):
            print("Aviso: el hilo de la camara no termino a tiempo")
        self.vision.free()

    # ------------------------------------------------------------------
    # Bucle del hilo / Thread loop
    # ------------------------------------------------------------------

    def _apply_request(self):
        """Abre, cambia o cierra la camara si lo pedido no coincide con lo que esta abierto"""
        """Opens, switches or closes the camera if the request doesn't match what's open"""
        wanted = self._requested_idx
        if wanted == self._opened_idx:
            return
        if self._opened_idx is not None:
            self.vision.free_camera()
            self.vision.reset_detections()
            self._opened_idx = None
        if wanted is not None:
            self.vision.start_camera(wanted)
            self._opened_idx = wanted

    def run(self):
        """Bucle principal del hilo de la camara"""
        """Main loop of the camera thread"""
        last_process = time.time()

        try:
            while not self._quit:
                try:
                    self._apply_request()
                except Exception as e:
                    print(f"Error abriendo/cerrando la camara: {e}")
                    self._opened_idx = None
                    time.sleep(0.5)
                    continue

                if self._opened_idx is None:
                    time.sleep(0.05)
                    continue

                try:
                    frame_bgr, frame_rgb, texts = self.vision.get_marked_frame(self.rotate)
                except Exception as e:
                    print(f"Error leyendo la camara: {e}")
                    frame_bgr, frame_rgb, texts = None, None, []

                # Si mientras se leia el frame se pidio otra camara o apagarla,
                # este frame ya no vale
                # If another camera or turning off was requested while reading
                # the frame, this frame is no longer valid
                if frame_rgb is not None and self._requested_idx == self._opened_idx:
                    self.new_frame.emit(frame_bgr, frame_rgb, texts)

                actual_time = time.time()
                if actual_time - last_process > 0.15:
                    self.vision.update_process()
                    last_process = actual_time

                time.sleep(0.015)
        finally:
            if self._opened_idx is not None:
                self.vision.free_camera()
                self._opened_idx = None
