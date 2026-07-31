import os, threading, time, numpy as np, sounddevice as sd, soundfile as sf
from faster_whisper import WhisperModel
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QThread
from dataclasses import dataclass
from models.audio import GestorVoz
from utils.constants import TipoEvento, ComandoVoz

@dataclass
class EventoInteraccion:
    tipo: TipoEvento
    texto: str = ""
    es_afirmativo: bool = False

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
        self.evento_actual = None 
        
        self.record_id = 0
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

    def _process_audio(self):
        try:
            sf.write(self.temp_file, np.array(self.audio_data), self.samplerate)
            segments, info = self.model.transcribe(self.temp_file, language="es")
            
            texto_transcrito = " ".join([segment.text for segment in segments]).strip().lower()
            texto_limpio = texto_transcrito.replace("?", "").replace("¿", "").replace("!", "").replace("¡", "").rstrip(".")
            
            print(f"[Voz detectada]: {texto_limpio}")
            
            evento_voz = EventoInteraccion(tipo=TipoEvento.VOZ, texto=texto_limpio)
            self.inyectar_evento(evento_voz)
            
        except Exception as e:
            print(f"Error procesando voz: {e}")
            if self.modo_dictado:
                self.evento_actual = EventoInteraccion(tipo=TipoEvento.VOZ, texto="")

    def _analizar_intencion(self, texto):
        if not texto: return
            
        if "foto" in texto or "capturar" in texto or "cámara" in texto:
            self.callback_comando(ComandoVoz.CAPTURAR)
        elif "enviar" in texto or "subir" in texto or "placa" in texto or "microbit" in texto:
            self.callback_comando(ComandoVoz.ENVIAR)
        elif "explicar" in texto or "inteligencia" in texto or "ia" in texto or "qué hace" in texto:
            self.callback_comando(ComandoVoz.EXPLICAR)
        elif "leer" in texto or "mesa" in texto or "qr" in texto:
            self.callback_comando(ComandoVoz.LEER)
        elif "voz" in texto or "audio" in texto or "hablar" in texto or "sonido" in texto:
            self.callback_comando(ComandoVoz.CAMBIAR_TTS)
        elif "repasar" in texto or "modificar" in texto or "variables" in texto:
            self.callback_comando(ComandoVoz.REPASAR)
        else:
            GestorVoz.leer_texto("Comando no reconocido.")

    @staticmethod
    def _interpretar_confirmacion(evento: EventoInteraccion):
        if evento.tipo == TipoEvento.OMITIR:
            return "omitir"
        if evento.tipo == TipoEvento.TOQUE_FISICO:
            return "confirmar" if evento.es_afirmativo else "repetir"
            
        valor = evento.texto.lower()
        if "pasar" in valor or "omitir" in valor:
            return "omitir"
        if "sí" in valor or "si" in valor or "correcto" in valor:
            return "confirmar"
        return "repetir"

    def start_dictation_record(self):
        if self.model is None or self.is_recording: return
        self.is_recording = True
        self.audio_data = []
        
        self.record_id = time.time()
        current_id = self.record_id
        
        def delayed_beep():
            time.sleep(0.4) 
            if self.is_recording and self.record_id == current_id: 
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

    def inyectar_evento(self, evento: EventoInteraccion):
        if self.modo_dictado:
            self.evento_actual = evento
        else:
            if evento.tipo == TipoEvento.VOZ and evento.texto:
                self._analizar_intencion(evento.texto)

    def escuchar_dictado_sincrono(self) -> EventoInteraccion:
        if self.callback_bloqueo_ui: 
            QTimer.singleShot(0, lambda: self.callback_bloqueo_ui(True))
            
        self.modo_dictado = True
        self.evento_actual = None
        
        try:
            while self.evento_actual is None:
                if QThread.currentThread() == QApplication.instance().thread():
                    QApplication.processEvents()
                time.sleep(0.05)
                
            return self.evento_actual
            
        finally:
            self.modo_dictado = False
            if self.callback_bloqueo_ui: 
                QTimer.singleShot(0, lambda: self.callback_bloqueo_ui(False))

    def bucle_confirmacion_voz(self, pregunta, valor_por_defecto="desconocido", es_pregunta_abierta=True):
        ultimo_texto = ""

        while True:
            GestorVoz.leer_texto(pregunta)
            respuesta: EventoInteraccion = self.escuchar_dictado_sincrono()

            if respuesta.tipo == TipoEvento.OMITIR:
                GestorVoz.leer_texto("Saltando paso. Usando valor por defecto.")
                return valor_por_defecto

            if es_pregunta_abierta:
                if respuesta.tipo == TipoEvento.TOQUE_FISICO:
                    GestorVoz.leer_texto("Por favor, dígame la respuesta hablando, no uses los toques rápidos.")
                    continue
                if not respuesta.texto:
                    continue
                ultimo_texto = respuesta.texto
            else:
                if respuesta.tipo == TipoEvento.TOQUE_FISICO:
                    return "sí" if respuesta.es_afirmativo else "no"
                    
                if not respuesta.texto:
                    continue
                    
                if respuesta.texto in ["sí", "si", "no", "pasar", "omitir"]:
                    return respuesta.texto
                ultimo_texto = respuesta.texto

            GestorVoz.leer_texto(f"He entendido {ultimo_texto}. ¿Es correcto?")
            confirmacion: EventoInteraccion = self.escuchar_dictado_sincrono()
            intencion = self._interpretar_confirmacion(confirmacion)

            if intencion == "confirmar":
                return ultimo_texto
            elif intencion == "omitir":
                GestorVoz.leer_texto("Omitiendo validación.")
                return ultimo_texto
            else:
                GestorVoz.leer_texto("De acuerdo, vamos a repetirlo.")