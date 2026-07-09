import os
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from core.audio import GestorVoz

class VoiceCommandManager:
    def __init__(self, callback_comando, workspace_dir):
        self.callback_comando = callback_comando
        self.is_recording = False
        self.audio_data = []
        self.samplerate = 16000
        self.stream = None
        self.temp_file = os.path.join(workspace_dir, "inputs", "temp_voice.wav")
        
        # Cargar el modelo en un hilo secundario para no congelar la interfaz de PyQt6
        self.model = None
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        print("Cargando motor de voz (Whisper Tiny)...")
        # El modelo 'tiny' es ultra rápido e ideal para ordenes cortas en CPU
        self.model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("Motor de voz listo.")

    def toggle_recording(self):
        if self.model is None:
            GestorVoz.leer_texto("El sistema de voz se está iniciando. Espera unos segundos.")
            return

        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self.is_recording = True
        self.audio_data = []
        GestorVoz.leer_texto("Te escucho")
        
        def audio_callback(indata, frames, time, status):
            self.audio_data.extend(indata.copy())

        self.stream = sd.InputStream(samplerate=self.samplerate, channels=1, callback=audio_callback)
        self.stream.start()

    def _stop_recording(self):
        self.is_recording = False
        self.stream.stop()
        self.stream.close()
        GestorVoz.leer_texto("Procesando")
        
        # Procesamos el audio en otro hilo para que la app siga siendo fluida
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        try:
            sf.write(self.temp_file, np.array(self.audio_data), self.samplerate)
            
            segments, info = self.model.transcribe(self.temp_file, language="es")
            texto_transcrito = " ".join([segment.text for segment in segments]).strip().lower()
            
            print(f"[Voz detectada]: {texto_transcrito}")
            self._analizar_intencion(texto_transcrito)
            
        except Exception as e:
            print(f"Error procesando voz: {e}")

    def _analizar_intencion(self, texto):
        if not texto:
            GestorVoz.leer_texto("No he escuchado nada.")
            return
            
        # Mapeo de procesamiento de lenguaje natural simple
        if "foto" in texto or "capturar" in texto or "cámara" in texto:
            self.callback_comando("capturar")
        elif "enviar" in texto or "subir" in texto or "placa" in texto or "microbit" in texto:
            self.callback_comando("enviar")
        elif "explicar" in texto or "inteligencia" in texto or "ia" in texto or "qué hace" in texto:
            self.callback_comando("explicar")
        elif "leer" in texto or "mesa" in texto or "qr" in texto:
            self.callback_comando("leer")
        else:
            GestorVoz.leer_texto("Comando no reconocido. Prueba a decir 'tomar foto' o 'explicar código'.")