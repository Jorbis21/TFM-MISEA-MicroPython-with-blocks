import serial, serial.tools.list_ports, threading, time

class SerialMonitor:

    def __init__(self, audio_service):
        self.audio_service = audio_service
        self.serial_port = None
        self.is_running = False
        self.thread = None
        self.baudrate = 115200 
  
    def start(self):
        """Inicia el demonio y gestiona el bucle"""
        """Starts the daemon y manages the loop"""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        print("[Serial] Demonio de escucha iniciado en segundo plano.")

    def stop(self):
        """Para el bucle"""
        """Stops the loop"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        print("[Serial] Monitor detenido.")

    def _interruptible_sleep(self, seconds):
        """Duerme por partes, comprobando is_running, para que stop() no tenga que esperar toda la espera de reintento de golpe"""
        """Sleeps in small chunks, checking is_running, so stop() doesn't have to wait out the full retry sleep at once"""
        steps = int(seconds / 0.1)
        for _ in range(steps):
            if not self.is_running:
                return
            time.sleep(0.1)

    def _search_microbit_port(self):
        """Busca el puerto en el que esta la Microbit conectada"""
        """Searchs the port where the Microbit is conected"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = port.description.lower()
            if "mbed" in desc or "micro:bit" in desc or "serial" in desc:
                return port.device
        
        if ports:
            return ports[0].device
        return None

    def _listen_loop(self):
        """Bucle infinito con reconexión automática"""
        """Infinite loop with automatic reconnection"""
        while self.is_running:
            if self.serial_port is None or not self.serial_port.is_open:
                dest_port = self._search_microbit_port()
                if dest_port:
                    try:
                        self.serial_port = serial.Serial(dest_port, self.baudrate, timeout=1)
                        print(f"[Serial] Micro:bit conectada con éxito en {dest_port}.")
                    except Exception:
                        pass
                
                if self.serial_port is None or not self.serial_port.is_open:
                    self._interruptible_sleep(2)
                    continue

            try:
                if self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line.startswith("TTS:"):
                        text_to_read = line.replace("TTS:", "").strip()
                        print(f"[Serial] Petición de lectura interceptada: {text_to_read}")
                        
                        self.audio_service.read_text(text_to_read)
                        
                        time.sleep(0.1) 
                        self.serial_port.write(b'\r\n')
                        self.serial_port.flush()
                        
            except serial.SerialException:
                print("[Serial] Cable desconectado. Esperando a que vuelva a conectarse...")
                if self.serial_port:
                    self.serial_port.close()
                self.serial_port = None
                self._interruptible_sleep(1)
            except Exception as e:
                print(f"[Serial] Error inesperado: {e}")
                
            time.sleep(0.05)