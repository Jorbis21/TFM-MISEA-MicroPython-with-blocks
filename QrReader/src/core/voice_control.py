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
    def __init__(self, callback_comando, workspace_dir, callback_bloqueo_ui=None):
        self.callback_comando = callback_comando
        self.callback_bloqueo_ui = callback_bloqueo_ui
        self.is_recording = False
        self.audio_data = []
        self.samplerate = 16000
        self.stream = None
        self.temp_file = os.path.join(workspace_dir, "inputs", "temp_voice.wav")
        
        self.modo_dictado = False
        # Usamos una palabra clave para detectar que no hay respuesta aún en vez de 'None' 
        # porque 'None' ahora significa "3 toques (Pasar)"
        self.texto_dictado = "___ESPERANDO___"
        
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

    def start_dictation_record(self):
        if self.model is None or self.is_recording: return
        self.is_recording = True
        self.audio_data = []
        
        def delayed_beep():
            time.sleep(0.4) 
            if self.is_recording: 
                try:
                    t = np.linspace(0, 0.15, int(self.samplerate * 0.15), False)
                    tone = np.sin(1000 * 2 * np.pi * t) * 0.5  
                    sd.play(tone, self.samplerate)
                except Exception as e:
                    print(f"Aviso: No se pudo reproducir el pitido de inicio: {e}")
                    
        threading.Thread(target=delayed_beep, daemon=True).start()
        
        def audio_callback(indata, frames, tiempo, status):
            self.audio_data.extend(indata.copy())
            
        self.stream = sd.InputStream(samplerate=self.samplerate, channels=1, callback=audio_callback)
        self.stream.start()

    def discard_dictation_record(self):
        if not self.is_recording: return
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.audio_data = []

    def stop_dictation_and_process(self):
        if not self.is_recording: return
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            
        GestorVoz.leer_texto("Procesando.")
        threading.Thread(target=self._process_audio, daemon=True).start()

    def set_texto_dictado(self, texto):
        print(f"[Comando inyectado por tap booleano]: {texto}")
        if self.modo_dictado:
            self.texto_dictado = texto
        else:
            if not isinstance(texto, bool) and texto is not None:
                self._analizar_intencion(texto)

    def _process_audio(self):
        try:
            sf.write(self.temp_file, np.array(self.audio_data), self.samplerate)
            
            segments, info = self.model.transcribe(
                self.temp_file, 
                language="es"
            )
            
            texto_transcrito = " ".join([segment.text for segment in segments]).strip().lower()
            texto_limpio = texto_transcrito.replace("?", "").replace("¿", "").replace("!", "").replace("¡", "")
            
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
        elif "voz" in texto or "audio" in texto or "hablar" in texto or "sonido" in texto:
            self.callback_comando("cambiar_tts")
        else:
            GestorVoz.leer_texto("Comando no reconocido.")

    def escuchar_dictado_sincrono(self):
        if self.callback_bloqueo_ui: self.callback_bloqueo_ui(True)
        self.modo_dictado = True
        self.texto_dictado = "___ESPERANDO___"
        try:
            while self.texto_dictado == "___ESPERANDO___":
                QApplication.processEvents()
                time.sleep(0.05)
            resultado = self.texto_dictado
            return resultado
        finally:
            self.modo_dictado = False
            if self.callback_bloqueo_ui: self.callback_bloqueo_ui(False)

    # --- NUEVA LÓGICA ESTRICTA BOOLEANA ---
    def bucle_confirmacion_voz(self, pregunta, valor_por_defecto="desconocido", es_pregunta_abierta=True):
        ultimo_texto = ""
        
        while True:
            GestorVoz.leer_texto(pregunta)
            
            respuesta = self.escuchar_dictado_sincrono()
            
            # Ignoramos si la voz detectó vacío
            if isinstance(respuesta, str) and not respuesta:
                continue
                
            es_toque_fisico = isinstance(respuesta, bool) or respuesta is None

            # FASE 1: Si pide un texto (Variable/Valor)
            if es_pregunta_abierta:
                if es_toque_fisico:
                    if respuesta is None: # 3 Taps (Pasar)
                        GestorVoz.leer_texto("Saltando paso. Usando valor por defecto.")
                        return valor_por_defecto
                    else: # 1 o 2 Taps (Sí/No)
                        GestorVoz.leer_texto("Por favor, dítame la respuesta hablando, no uses los toques rápidos.")
                        continue
                
                # Respuesta por voz
                if respuesta in ["pasar", "omitir"]:
                    GestorVoz.leer_texto("Saltando paso. Usando valor por defecto.")
                    return valor_por_defecto
                    
                ultimo_texto = respuesta

            # FASE 2: Si pide una decisión Sí/No (Como ampliar la cámara)
            else:
                if es_toque_fisico:
                    if respuesta is True: return "sí"
                    if respuesta is False: return "no"
                    if respuesta is None: return "pasar"
                    
                # Respuesta por voz
                if respuesta in ["sí", "si", "no", "pasar", "omitir"]:
                    return respuesta
                    
                ultimo_texto = respuesta

            # FASE 3: CONFIRMACIÓN (Doble verificación para textos)
            GestorVoz.leer_texto(f"He entendido {ultimo_texto}. ¿Es correcto?")
            confirmacion = self.escuchar_dictado_sincrono()
            
            conf_es_toque = isinstance(confirmacion, bool) or confirmacion is None

            if conf_es_toque:
                if confirmacion is True: # 2 Taps
                    return ultimo_texto
                elif confirmacion is None: # 3 Taps
                    GestorVoz.leer_texto("Omitiendo validación.")
                    return ultimo_texto
                else: # 1 Tap (False)
                    GestorVoz.leer_texto("De acuerdo, vamos a repetirlo.")
                    continue
            else:
                # Confirmación por voz
                if "sí" in confirmacion or "si" in confirmacion or "correcto" in confirmacion:
                    return ultimo_texto
                elif "pasar" in confirmacion or "omitir" in confirmacion:
                    GestorVoz.leer_texto("Omitiendo validación.")
                    return ultimo_texto
                else:
                    GestorVoz.leer_texto("De acuerdo, vamos a repetirlo.")