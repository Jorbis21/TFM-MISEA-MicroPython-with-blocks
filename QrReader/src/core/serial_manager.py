import serial
import serial.tools.list_ports
import threading
import time
from core.audio import GestorVoz

class SerialMonitor:
    def __init__(self):
        self.serial_port = None
        self.is_running = False
        self.thread = None
        self.baudrate = 115200 

    def _buscar_puerto_microbit(self):
        """Busca automáticamente el puerto COM donde está conectada la Micro:bit."""
        puertos = serial.tools.list_ports.comports()
        for puerto in puertos:
            desc = puerto.description.lower()
            if "mbed" in desc or "micro:bit" in desc or "serial" in desc:
                return puerto.device
        
        if puertos:
            return puertos[0].device
        return None

    def arrancar(self):
        """Inicia el demonio en segundo plano. La conexión física se gestiona en el bucle."""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._bucle_escucha, daemon=True)
        self.thread.start()
        print("[Serial] Demonio de escucha iniciado en segundo plano.")

    def detener(self):
        """Detiene el bucle y libera el puerto USB."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        print("[Serial] Monitor detenido.")

    def _bucle_escucha(self):
        """Bucle infinito con reconexión automática (Plug & Play)."""
        while self.is_running:
            # 1. FASE DE RECONEXIÓN: Si no hay puerto abierto, lo buscamos sin parar
            if self.serial_port is None or not self.serial_port.is_open:
                puerto_destino = self._buscar_puerto_microbit()
                if puerto_destino:
                    try:
                        self.serial_port = serial.Serial(puerto_destino, self.baudrate, timeout=1)
                        print(f"[Serial] Micro:bit conectada con éxito en {puerto_destino}.")
                    except Exception:
                        pass
                
                # Si sigue sin haber puerto, esperamos 2 segundos y volvemos a intentarlo
                if self.serial_port is None or not self.serial_port.is_open:
                    time.sleep(2)
                    continue

            # 2. FASE DE LECTURA: Si estamos conectados, escuchamos el TTS
            try:
                if self.serial_port.in_waiting > 0:
                    linea = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    
                    if linea.startswith("TTS:"):
                        texto_a_leer = linea.replace("TTS:", "").strip()
                        print(f"[Serial] Petición de lectura interceptada: {texto_a_leer}")
                        
                        GestorVoz.leer_texto(texto_a_leer)
                        
                        time.sleep(0.1) 
                        self.serial_port.write(b'\r\n')
                        self.serial_port.flush()
                        
            except serial.SerialException:
                # Si el usuario tira del cable, cerramos el puerto de forma segura.
                # En la siguiente vuelta del 'while', entrará en la FASE DE RECONEXIÓN automáticamente.
                print("[Serial] Cable desconectado. Esperando a que vuelva a conectarse...")
                if self.serial_port:
                    self.serial_port.close()
                self.serial_port = None
                time.sleep(1)
            except Exception as e:
                print(f"[Serial] Error inesperado: {e}")
                
            time.sleep(0.05)