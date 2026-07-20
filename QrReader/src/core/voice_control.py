import os
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from core.audio import GestorVoz

class VoiceCommandManager:
    '''Inicializacion'''
    def __init__(self, callback_comando, workspace_dir):
        self.callback_comando = callback_comando
        self.is_recording = False
        self.audio_data = []
        self.samplerate = 16000
        self.stream = None
        self.temp_file = os.path.join(workspace_dir, "inputs", "temp_voice.wav")
        
        self.model = None
        threading.Thread(target=self._load_model, daemon=True).start()

    '''Metodo para cargar el motor de voz'''
    def _load_model(self):
        print("Cargando motor de voz (Whisper Medium)...")
        self.model = WhisperModel(
            "medium", 
            device="cpu", 
            compute_type="int8", 
            cpu_threads=4
        )
        print("Motor de voz listo.")
        GestorVoz.leer_texto("El control por voz esta listo.")


    '''Metodo para la gestion de la recepcion de la voz'''
    def toggle_recording(self):
        if self.model is None:
            GestorVoz.leer_texto("El sistema de voz se está iniciando. Espera unos segundos.")
            return

        if not self.is_recording:
            GestorVoz.leer_texto("Te escucho.")
            self._start_recording()
        else:
            self._stop_recording()

    '''Metodo para grabar la voz'''
    def _start_recording(self):
        self.is_recording = True
        self.audio_data = []
        
        def audio_callback(indata, frames, time, status):
            self.audio_data.extend(indata.copy())

        self.stream = sd.InputStream(samplerate=self.samplerate, channels=1, callback=audio_callback)
        self.stream.start()

    '''Metodo para dejar de grabar la voz'''
    def _stop_recording(self):
        self.is_recording = False
        self.stream.stop()
        self.stream.close()
        GestorVoz.leer_texto("Procesando")
        
        threading.Thread(target=self._process_audio, daemon=True).start()

    '''Metodo para procesar el audio y analizar la intencion'''
    def _process_audio(self):
        try:
            sf.write(self.temp_file, np.array(self.audio_data), self.samplerate)
            
            segments, info = self.model.transcribe(self.temp_file, language="es")
            texto_transcrito = " ".join([segment.text for segment in segments]).strip().lower()
            
            print(f"[Voz detectada]: {texto_transcrito}")
            self._analizar_intencion(texto_transcrito)
            
        except Exception as e:
            print(f"Error procesando voz: {e}")

    '''Metodo para saber que accion realizar'''
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
    
    def escuchar_dictado_sincrono(self, timeout=5):
        """Graba un clip de audio de longitud fija (síncrono) para capturar respuestas rápidas."""
        import time
        GestorVoz.leer_texto("Piii") # Feedback sonoro opcional
        time.sleep(0.5) # Espera a que termine el pitido
        
        audio_capturado = sd.rec(int(timeout * self.samplerate), samplerate=self.samplerate, channels=1)
        sd.wait() # Bloquea la ejecución hasta grabar los 'timeout' segundos
        
        try:
            sf.write(self.temp_file, audio_capturado, self.samplerate)
            segments, _ = self.model.transcribe(self.temp_file, language="es")
            texto_transcrito = " ".join([segment.text for segment in segments]).strip().lower()
            # Limpiamos puntuación básica generada por Whisper
            texto_limpio = texto_transcrito.replace(".", "").replace(",", "").replace("?", "").replace("¿", "")
            print(f"[Dictado Capturado]: {texto_limpio}")
            return texto_limpio
        except Exception as e:
            print(f"Error en dictado síncrono: {e}")
            return ""

    def bucle_confirmacion_voz(self, pregunta):
        """
        Implementa el Flujo Principal (Pregunta -> Escucha -> Confirmación).
        Retorna el texto final validado.
        """
        import time
        ultimo_texto = ""
        
        while True:
            # 1. Petición
            GestorVoz.leer_texto(pregunta)
            time.sleep(2) # Espera activa aprox para que termine de hablar
            
            # 2. Escucha
            texto_detectado = self.escuchar_dictado_sincrono(timeout=4)
            if not texto_detectado:
                continue
                
            ultimo_texto = texto_detectado
            
            # 3. Confirmación
            GestorVoz.leer_texto(f"He entendido {texto_detectado}. ¿Es correcto?")
            time.sleep(2.5)
            
            confirmacion = self.escuchar_dictado_sincrono(timeout=3)
            
            # 4. Árbol de Decisión
            if "sí" in confirmacion or "si" in confirmacion or "correcto" in confirmacion:
                return ultimo_texto
            elif "pasar" in confirmacion or "omitir" in confirmacion:
                GestorVoz.leer_texto("Omitiendo validación. Utilizando último texto detectado.")
                return ultimo_texto
            else:
                GestorVoz.leer_texto("De acuerdo, vamos a repetirlo.")
                time.sleep(1.5)
                # El bucle while vuelve a empezar (Respuesta NO)