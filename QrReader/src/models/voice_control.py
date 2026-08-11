import os, threading, time, numpy as np, soundfile as sf
from faster_whisper import WhisperModel
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QThread
from dataclasses import dataclass

from utils.constants import EventType, VoiceCommand

@dataclass
class InteractionEvent:
    type: EventType
    text: str = ""
    afirmative: bool = False

class VoiceCommandManager:

    def __init__(self, callback_command, workspace_dir, audio_service, callback_freeze_ui=None):
        self.callback_command = callback_command
        self.callback_freeze_ui = callback_freeze_ui
        self.audio_service = audio_service
        self.is_recording = False
        self.audio_data = []
        self.samplerate = 16000
        self.stream = None
        self.temp_file = os.path.join(workspace_dir, "inputs", "temp_voice.wav")
        
        self.dictation_mode = False
        self.actual_event = None 
        self.running = True
        
        self.record_id = 0
        self.model = None
        threading.Thread(target=self._load_model, daemon=True).start()

    def stop(self):
        """Para the grabar y descarta la grabacion"""
        """Stops recording and discards the record"""
        self.running = False
        self.discard_dictation_record()

    def _load_model(self):
        """Carga el modelo de Whisper"""
        """Loads the Whisper model"""
        print("Cargando motor de voz (Whisper Medium)...")
        self.model = WhisperModel(
            "medium", 
            device="cpu", 
            compute_type="int8", 
            cpu_threads=4
        )
        print("Motor de voz listo.")
        self.audio_service.read_text("El control por voz está listo.")

    def _process_audio(self):
        """Procesa y limpia el audio"""
        """Process and cleans the audio"""
        try:
            sf.write(self.temp_file, np.array(self.audio_data), self.samplerate)
            segments, info = self.model.transcribe(self.temp_file, language="es")
            
            transcribed_text = " ".join([segment.text for segment in segments]).strip().lower()
            clean_text = transcribed_text.replace("?", "").replace("¿", "").replace("!", "").replace("¡", "").rstrip(".")
            
            print(f"[Voz detectada]: {clean_text}")
            
            voice_event = InteractionEvent(type=EventType.VOICE, text=clean_text)
            self.inject_event(voice_event)
            
        except Exception as e:
            print(f"Error procesando voz: {e}")
            if self.dictation_mode:
                self.actual_event = InteractionEvent(type=EventType.VOICE, text="")

    def _analize_intetion(self, text):
        """Decide cual es la intencion del usuario"""
        """Decides what's the user intention"""
        if not text: return
            
        spacing_text = f" {text} "
            
        if "foto" in text or "capturar" in text or "cámara" in text:
            self.callback_command(VoiceCommand.CAPTURE)
        elif "enviar" in text or "subir" in text or "placa" in text or "microbit" in text:
            self.callback_command(VoiceCommand.SEND)
        elif "explicar" in text or "inteligencia" in text or " ia " in spacing_text or "qué hace" in text:
            self.callback_command(VoiceCommand.EXPLAIN)
        elif "leer" in text or "mesa" in text or "qr" in text:
            self.callback_command(VoiceCommand.READ)
        elif "voz" in text or "audio" in text or "hablar" in text or "sonido" in text:
            self.callback_command(VoiceCommand.CHANGE_TTS)
        elif "repasar" in text or "modificar" in text or "variables" in text:
            self.callback_command(VoiceCommand.REVIEW)
        else:
            self.audio_service.read_text("Comando no reconocido.")

    @staticmethod
    def _interpret_confirmation(event: InteractionEvent):
        """Decide como avanzar en las interacciones"""
        """Decides how to continue with the interactions"""
        if event.type == EventType.SKIP:
            return "omitir"
        if event.type == EventType.TAP:
            return "confirmar" if event.afirmative else "repetir"
            
        value = event.text.lower()
        if "pasar" in value or "omitir" in value:
            return "omitir"
        if "sí" in value or "si" in value or "correcto" in value:
            return "confirmar"
        return "repetir"

    def start_dictation_record(self):
        """Comienza la grabacion del audio"""
        """Starts the audio recording"""
        if self.model is None or self.is_recording: return
        self.is_recording = True
        self.audio_data = []
        
        self.record_id = time.time()
        current_id = self.record_id
        
        def delayed_beep():
            time.sleep(0.4) 
            if self.is_recording and self.record_id == current_id: 
                try:
                    import numpy as np
                    import sounddevice as sd
                    t = np.linspace(0, 0.15, int(self.samplerate * 0.15), False)
                    tone = np.sin(1000 * 2 * np.pi * t) * 0.5  
                    sd.play(tone, self.samplerate)
                except Exception as e:
                    print(f"Aviso: No se pudo reproducir el pitido de inicio: {e}")
                    
        threading.Thread(target=delayed_beep, daemon=True).start()
        
        def audio_callback(indata, frames, tiempo, status):
            self.audio_data.extend(indata.copy())
            
        def _start_hardware():
            import sounddevice as sd
            try:
                new_stream = sd.InputStream(samplerate=self.samplerate, channels=1, callback=audio_callback)
                new_stream.start()

                if self.is_recording and self.record_id == current_id:
                    self.stream = new_stream
                else:
                    new_stream.stop()
                    new_stream.close()
            except Exception as e:
                print(f"Error accediendo al micrófono: {e}")

        threading.Thread(target=_start_hardware, daemon=True).start()

    def discard_dictation_record(self):
        """Descarta el audio grabado"""
        """Discards the recorded audio"""
        if not self.is_recording: return
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception: pass
            self.stream = None
        self.audio_data = []

    def stop_dictation_and_process(self):
        """Para de grabar y procesa el audio"""
        """Stops recording and process the audio"""
        if not self.is_recording: return
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception: pass
            self.stream = None
            
        self.audio_service.read_text("Procesando.")
        threading.Thread(target=self._process_audio, daemon=True).start()

    def inject_event(self, event: InteractionEvent):
        """Inyecta el evento"""
        """Inyects the event"""
        if self.dictation_mode:
            self.actual_event = event
        else:
            if event.type == EventType.VOICE and event.text:
                self._analize_intetion(event.text)

    def listen_dict_sync(self) -> InteractionEvent:
        """Escucha la grabacion sincronamente"""
        """listens the recording synchronously"""
        if self.callback_freeze_ui: 
            QTimer.singleShot(0, lambda: self.callback_freeze_ui(True))
            
        self.dictation_mode = True
        self.actual_event = None
        
        try:
            while self.actual_event is None and self.running:
                if QThread.currentThread() == QApplication.instance().thread():
                    QApplication.processEvents()
                time.sleep(0.05)

            if not self.running:
                return InteractionEvent(type=EventType.SKIP)
                
            return self.actual_event
            
        finally:
            self.dictation_mode = False
            if self.callback_freeze_ui: 
                QTimer.singleShot(0, lambda: self.callback_freeze_ui(False))

    def voice_confirmation_loop(self, question, default_value="desconocido", open_question=True):
        """Bucle de confirmacion de variables"""
        """Variables confirmation loop"""
        last_text = ""

        while True:
            self.audio_service.read_text(question)
            answer: InteractionEvent = self.listen_dict_sync()

            if answer.type == EventType.SKIP:
                self.audio_service.read_text("Saltando paso. Usando valor por defecto.")
                return default_value

            if open_question:
                if answer.type == EventType.TAP:
                    self.audio_service.read_text("Por favor, dígame la respuesta hablando, no uses los toques rápidos.")
                    continue
                if not answer.text:
                    continue
                last_text = answer.text
            else:
                if answer.type == EventType.TAP:
                    return "sí" if answer.afirmative else "no"
                    
                if not answer.text:
                    continue
                    
                if answer.text in ["sí", "si", "no", "pasar", "omitir"]:
                    return answer.text
                last_text = answer.text

            self.audio_service.read_text(f"He entendido {last_text}. ¿Es correcto?")
            confirm: InteractionEvent = self.listen_dict_sync()
            intention = self._interpret_confirmation(confirm)

            if intention == "confirmar":
                return last_text
            elif intention == "omitir":
                self.audio_service.read_text("Omitiendo validación.")
                return last_text
            else:
                self.audio_service.read_text("De acuerdo, vamos a repetirlo.")