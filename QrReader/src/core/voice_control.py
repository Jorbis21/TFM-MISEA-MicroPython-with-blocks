import os
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from PyQt6.QtWidgets import QApplication
import time
from core.audio import GestorVoz

class VoiceCommandManager:
    def __init__(self, callback_comando, workspace_dir):
        self.callback_comando = callback_comando
        self.is_recording = False
        self.audio_data = []
        self.samplerate = 16000
        self.stream = None
        self.temp_file = os.path.join(workspace_dir, "inputs", "temp_voice.wav")
        
        # Estado de dictado interactivo
        self.modo_dictado = False
        self.texto_dictado = None
        
        self.model = None
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        print("Cargando motor de voz (Whisper Medium)...")
        self.model = WhisperModel(
            "medium", 
            device="cpu", 
            compute_type="int8", 
            cpu_threads=4
        )
        print("Motor de voz listo.")
        GestorVoz.leer_texto("El control por voz está listo.")

    # ========================================================
    # SISTEMA HOLD-TO-TALK Y TAPS
    # ========================================================
    def start_dictation_record(self):
        """Inicia la grabación y emite un pitido solo si se mantiene pulsado (HOLD)."""
        if self.model is None or self.is_recording: return
        self.is_recording = True
        self.audio_data = []
        
        # Función en segundo plano para comprobar si realmente quieres hablar
        def delayed_beep():
            time.sleep(0.4) # Esperamos a ver si es un toque corto
            if self.is_recording: # Si sigues grabando después de 0.4s, es un HOLD
                try:
                    t = np.linspace(0, 0.15, int(self.samplerate * 0.15), False)
                    tone = np.sin(1000 * 2 * np.pi * t) * 0.5  
                    sd.play(tone, self.samplerate)
                except Exception as e:
                    print(f"Aviso: No se pudo reproducir el pitido de inicio: {e}")
                    
        # Lanzamos el comprobador de pitido sin bloquear el audio
        threading.Thread(target=delayed_beep, daemon=True).start()
        
        def audio_callback(indata, frames, tiempo, status):
            self.audio_data.extend(indata.copy())
            
        self.stream = sd.InputStream(samplerate=self.samplerate, channels=1, callback=audio_callback)
        self.stream.start()

    def discard_dictation_record(self):
        """Descarta el audio si fue solo un toque corto (TAP)."""
        if not self.is_recording: return
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.audio_data = []

    def stop_dictation_and_process(self):
        """Termina la grabación larga (HOLD), avisa al usuario y la procesa con Whisper."""
        if not self.is_recording: return
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            
        # Aviso sonoro de que ha terminado de escuchar
        GestorVoz.leer_texto("Procesando.")
            
        threading.Thread(target=self._process_audio, daemon=True).start()

    def set_texto_dictado(self, texto):
        """Inyecta un comando directo por toques de espacio (1=sí, 2=no, 3=pasar)."""
        print(f"[Comando inyectado por tap]: {texto}")
        if self.modo_dictado:
            self.texto_dictado = texto
        else:
            self._analizar_intencion(texto)

    def _process_audio(self):
        try:
            sf.write(self.temp_file, np.array(self.audio_data), self.samplerate)
            
            segments, info = self.model.transcribe(
                self.temp_file, 
                language="es"
            )
            
            texto_transcrito = " ".join([segment.text for segment in segments]).strip().lower()
            
            # --- LA CORRECCIÓN ESTÁ AQUÍ ---
            # Quitamos interrogaciones y exclamaciones, pero dejamos las comas y los puntos decimales
            texto_limpio = texto_transcrito.replace("?", "").replace("¿", "").replace("!", "").replace("¡", "")
            
            # Whisper suele poner un punto final al terminar de hablar. Lo quitamos si está al final del todo.
            if texto_limpio.endswith("."):
                texto_limpio = texto_limpio[:-1]
                
            print(f"[Voz detectada]: {texto_limpio}")
            
            if self.modo_dictado:
                self.texto_dictado = texto_limpio
            else:
                self._analizar_intencion(texto_limpio)
            
        except Exception as e:
            print(f"Error procesando voz: {e}")
            if self.modo_dictado:
                self.texto_dictado = ""

    def _analizar_intencion(self, texto):
        if not texto: return
            
        if "foto" in texto or "capturar" in texto or "cámara" in texto:
            self.callback_comando("capturar")
        elif "enviar" in texto or "subir" in texto or "placa" in texto or "microbit" in texto:
            self.callback_comando("enviar")
        elif "explicar" in texto or "inteligencia" in texto or "ia" in texto or "qué hace" in texto:
            self.callback_comando("explicar")
        elif "leer" in texto or "mesa" in texto or "qr" in texto:
            self.callback_comando("leer")
        # --- NUEVO: Palabras clave para alternar el TTS ---
        elif "voz" in texto or "audio" in texto or "hablar" in texto or "sonido" in texto:
            self.callback_comando("cambiar_tts")
        # --------------------------------------------------
        else:
            GestorVoz.leer_texto("Comando no reconocido.")

    # ========================================================
    # DICTADO INTERACTIVO SÍNCRONO
    # ========================================================
    def escuchar_dictado_sincrono(self):
        """Bloquea la compilación en segundo plano hasta que el usuario responda con toques o hablando."""
        self.modo_dictado = True
        self.texto_dictado = None
        
        while self.texto_dictado is None:
            QApplication.processEvents()
            time.sleep(0.05)
            
        resultado = self.texto_dictado
        self.modo_dictado = False
        return resultado

    def bucle_confirmacion_voz(self, pregunta):
        ultimo_texto = ""
        
        while True:
            GestorVoz.leer_texto(pregunta)
            
            texto_detectado = self.escuchar_dictado_sincrono()
            if not texto_detectado:
                continue
                
            ultimo_texto = texto_detectado
            
            GestorVoz.leer_texto(f"He entendido {texto_detectado}. ¿Es correcto?")
            
            confirmacion = self.escuchar_dictado_sincrono()
            
            if "sí" in confirmacion or "si" in confirmacion or "correcto" in confirmacion:
                return ultimo_texto
            elif "pasar" in confirmacion or "omitir" in confirmacion:
                GestorVoz.leer_texto("Omitiendo validación.")
                return ultimo_texto
            else:
                GestorVoz.leer_texto("De acuerdo, vamos a repetirlo.")