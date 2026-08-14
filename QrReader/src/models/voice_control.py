import os, re, threading, time, numpy as np, soundfile as sf
from faster_whisper import WhisperModel
from dataclasses import dataclass

from utils.constants import EventType, VoiceCommand
from utils.strings import t
from utils.language import get_language
from utils.main_thread import pump_events_if_on_main_thread

@dataclass
class InteractionEvent:
    """Resultado de una interacción por voz o táctil: qué tipo de evento fue, qué se dijo (si algo), y si fue una confirmación afirmativa"""
    """Result of a voice or tap interaction: what kind of event it was, what was said (if anything), and whether it was an affirmative confirmation"""
    type: EventType
    text: str = ""
    afirmative: bool = False

class VoiceCommandManager:
    """Graba y transcribe audio con Whisper, reconoce comandos e intenciones a partir del texto, y gestiona el ciclo de grabación/dictado que usa el resto de la aplicación para interactuar por voz"""
    """Records and transcribes audio with Whisper, recognizes commands and intentions from the text, and manages the recording/dictation cycle the rest of the application uses to interact by voice"""

    def __init__(self, callback_command, workspace_dir, audio_service, callback_freeze_ui=None):
        """Guarda las referencias necesarias y arranca en un hilo aparte la carga del modelo de Whisper, que puede tardar unos segundos"""
        """Stores the necessary references and starts loading the Whisper model on a separate thread, which can take a few seconds"""
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
        """Detiene el gestor de voz y descarta cualquier grabación de dictado que estuviera en curso"""
        """Stops the voice manager and discards any dictation recording in progress"""
        self.running = False
        self.discard_dictation_record()

    def _load_model(self):
        """Carga el modelo de Whisper en segundo plano y avisa por voz cuando el control por voz ya está listo"""
        """Loads the Whisper model in the background and announces by voice once voice control is ready"""
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
        """Guarda el audio grabado a disco, lo transcribe con Whisper en el idioma activo, limpia el texto resultante, y lo despacha como evento de interacción"""
        """Saves the recorded audio to disk, transcribes it with Whisper in the active language, cleans up the resulting text, and dispatches it as an interaction event"""
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
        """Busca en el texto transcrito alguna de las palabras clave de cada comando y dispara el correspondiente; si no reconoce ninguna, avisa de que no se ha entendido"""
        """Looks in the transcribed text for any of each command's keywords and triggers the matching one; if none is recognized, announces that it wasn't understood"""
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
        """Traduce un evento de interacción a una de tres respuestas neutras (confirm/retry/skip), sea cual sea el idioma o si vino por voz o por toque físico"""
        """Translates an interaction event into one of three neutral responses (confirm/retry/skip), regardless of language or whether it came by voice or physical tap"""
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
        """Empieza a grabar audio del micrófono en un hilo aparte, con un pitido corto de confirmación tras un breve retraso para no cortar el inicio de lo que diga el usuario"""
        """Starts recording audio from the microphone on a separate thread, with a short confirmation beep after a brief delay so it doesn't cut off the start of what the user says"""
        if self.model is None or self.is_recording: return
        self.is_recording = True
        self.audio_data = []
        
        self.record_id = time.time()
        current_id = self.record_id
        
        def delayed_beep():
            """Reproduce el pitido de confirmación de inicio, solo si la grabación sigue siendo la misma (no se ha cancelado ni empezado otra)"""
            """Plays the start-confirmation beep, only if the recording is still the same one (hasn't been cancelled or a new one started)"""
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
            """Acumula cada bloque de audio que llega del micrófono mientras dura la grabación"""
            """Accumulates each audio block coming from the microphone while the recording lasts"""
            self.audio_data.extend(indata.copy())
            
        def _start_hardware():
            """Abre el flujo de audio del micrófono en segundo plano; si mientras tanto la grabación se canceló o empezó otra, cierra el flujo sin usarlo"""
            """Opens the microphone audio stream in the background; if meanwhile the recording was cancelled or another one started, closes the stream without using it"""
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
        """Para la grabación en curso y descarta el audio capturado, sin transcribirlo"""
        """Stops the recording in progress and discards the captured audio, without transcribing it"""
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
        """Para la grabación y lanza la transcripción del audio capturado en un hilo aparte, avisando primero de que se está procesando"""
        """Stops the recording and launches the transcription of the captured audio on a separate thread, first announcing that it's being processed"""
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
        """Entrega un evento de interacción: si se está esperando un dictado, lo guarda para que listen_dict_sync lo recoja; si no, lo interpreta como un comando normal"""
        """Delivers an interaction event: if a dictation is being awaited, stores it for listen_dict_sync to pick up; otherwise, interprets it as a normal command"""
        if self.dictation_mode:
            self.actual_event = event
        else:
            if event.type == EventType.VOICE and event.text:
                self._analyze_intention(event.text)

    def listen_dict_sync(self) -> InteractionEvent:
        """Bloquea hasta que llegue un evento de interacción (voz o toque), manteniendo la interfaz respondiendo mientras espera si se llama desde el hilo principal"""
        """Blocks until an interaction event arrives (voice or tap), keeping the interface responsive while it waits if called from the main thread"""
        if self.callback_freeze_ui: 
            self.callback_freeze_ui(True)
            
        self.dictation_mode = True
        self.actual_event = None
        
        try:
            while self.actual_event is None and self.running:
                pump_events_if_on_main_thread()
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