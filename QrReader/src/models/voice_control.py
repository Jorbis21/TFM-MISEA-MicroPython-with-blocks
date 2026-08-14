import os, re, threading, time, numpy as np, soundfile as sf
from faster_whisper import WhisperModel
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread
from dataclasses import dataclass

from utils.constants import EventType, VoiceCommand
from utils.strings import t
from utils.language import get_language

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
        self.running = False
        self.discard_dictation_record()

    def _load_model(self):
        print("Cargando motor de voz (Whisper Medium)...")
        self.model = WhisperModel(
            "medium", 
            device="cpu", 
            compute_type="int8", 
            cpu_threads=4
        )
        print("Motor de voz listo.")
        self.audio_service.read_text(t("voice_ready"))

    def _process_audio(self):
        try:
            sf.write(self.temp_file, np.array(self.audio_data), self.samplerate)
            segments, info = self.model.transcribe(self.temp_file, language=get_language())
            
            transcribed_text = " ".join([segment.text for segment in segments]).strip().lower()
            clean_text = transcribed_text.replace("?", "").replace("¿", "").replace("!", "").replace("¡", "").rstrip(".")
            
            print(f"[Voz detectada]: {clean_text}")
            
            voice_event = InteractionEvent(type=EventType.VOICE, text=clean_text)
            self.inject_event(voice_event)
            
        except Exception as e:
            print(f"Error procesando voz: {e}")
            if self.dictation_mode:
                self.actual_event = InteractionEvent(type=EventType.VOICE, text="")

    def _analyze_intention(self, text):
        if not text: return

        words = set(re.findall(r"[\wáéíóúñ]+", text.lower()))

        if words & set(t("kw_capture")):
            self.callback_command(VoiceCommand.CAPTURE)
        elif words & set(t("kw_send")):
            self.callback_command(VoiceCommand.SEND)
        elif words & set(t("kw_explain")) or t("kw_explain_phrase") in text:
            self.callback_command(VoiceCommand.EXPLAIN)
        elif words & set(t("kw_read")):
            self.callback_command(VoiceCommand.READ)
        elif words & set(t("kw_tts")):
            self.callback_command(VoiceCommand.CHANGE_TTS)
        elif words & set(t("kw_review")):
            self.callback_command(VoiceCommand.REVIEW)
        else:
            self.audio_service.read_text(t("command_not_recognized"))

    @staticmethod
    def _interpret_confirmation(event: InteractionEvent):
        if event.type == EventType.SKIP:
            return "skip"
        if event.type == EventType.TAP:
            return "confirm" if event.afirmative else "retry"

        tokens = set(re.findall(r"[\wáéíóúñ]+", event.text.lower()))
        if tokens & set(t("kw_skip")):
            return "skip"
        if tokens & set(t("kw_yes")):
            return "confirm"
        return "retry"

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
        if not self.is_recording: return
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception: pass
            self.stream = None
            
        self.audio_service.read_text(t("processing"))
        threading.Thread(target=self._process_audio, daemon=True).start()

    def inject_event(self, event: InteractionEvent):
        if self.dictation_mode:
            self.actual_event = event
        else:
            if event.type == EventType.VOICE and event.text:
                self._analyze_intention(event.text)

    def listen_dict_sync(self) -> InteractionEvent:
        if self.callback_freeze_ui: 
            self.callback_freeze_ui(True)
            
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
                self.callback_freeze_ui(False)

    def voice_confirmation_loop(self, pregunta, valor_por_defecto="desconocido"):
        """Hace una pregunta de texto libre y confirma la respuesta reconocida antes de devolverla"""
        """Asks a free-text question and confirms the recognized answer before returning it"""
        last_text = ""

        while True:
            self.audio_service.read_text(pregunta)
            answer: InteractionEvent = self.listen_dict_sync()

            if answer.type == EventType.SKIP:
                self.audio_service.read_text(t("skip_using_default"))
                return valor_por_defecto

            if answer.type == EventType.TAP:
                self.audio_service.read_text(t("tap_not_allowed_speak"))
                continue
            if not answer.text:
                continue
            last_text = answer.text

            self.audio_service.read_text(t("understood_confirm", text=last_text))
            confirm: InteractionEvent = self.listen_dict_sync()
            intention = self._interpret_confirmation(confirm)

            if intention == "confirm":
                return last_text
            elif intention == "skip":
                self.audio_service.read_text(t("skipping_validation"))
                return last_text
            else:
                self.audio_service.read_text(t("lets_repeat"))

    def confirm_yes_no(self, pregunta, default=False):
        """Hace una pregunta cerrada de sí/no y devuelve un booleano, sin depender de qué palabra concreta se reconoció"""
        """Asks a closed yes/no question and returns a boolean, independent of which specific word was recognized"""
        yes_words = set(t("kw_yes"))
        skip_words = set(t("kw_skip"))

        while True:
            self.audio_service.read_text(pregunta)
            answer: InteractionEvent = self.listen_dict_sync()

            if answer.type == EventType.SKIP:
                self.audio_service.read_text(t("skip_using_default"))
                return default

            if answer.type == EventType.TAP:
                return answer.afirmative

            if not answer.text:
                continue

            tokens = set(re.findall(r"[\wáéíóúñ]+", answer.text.lower()))
            if tokens & skip_words:
                self.audio_service.read_text(t("skip_using_default"))
                return default
            if tokens & yes_words:
                return True
            if "no" in tokens:
                return False

            self.audio_service.read_text(t("lets_repeat"))