import os, asyncio, threading, uuid, tempfile, edge_tts, pygame, pyttsx3, queue, time, json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from utils.code_text import strip_static_header
from utils.language import get_language, get_voice
from utils.strings import t

class AudioService:

    def __init__(self, assets_dir):
        self.VOICE = get_voice()
        
        pygame.mixer.init()
        self.tts_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        
        self.CACHE_DIR = os.path.join(assets_dir, 'audio_cache', get_language())
        self.INDEX_FILE = os.path.join(self.CACHE_DIR, 'index.json')
        
        self.cache_sentences = {}
        # Varios hilos, no uno: si una descarga se cuelga y se abandona por
        # timeout, su hilo sigue ocupado indefinidamente. Con un solo hilo,
        # todos los reintentos posteriores harian cola detras de la colgada
        # y agotarian el timeout tambien, impidiendo recuperar Edge-TTS
        # aunque volviese la conexion.
        self._tts_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="edge_tts")
        # Ejecutor aparte y con varios hilos para la generacion offline: si
        # una llamada a pyttsx3 se cuelga (ocurre), ocupa uno de los hilos
        # pero las frases siguientes pueden seguir generandose en los otros,
        # en vez de quedar todas atrapadas detras de la colgada.
        self._offline_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="offline_tts")
        self._edge_tts_retry_at = 0
        if os.path.exists(self.INDEX_FILE):
            try:
                with open(self.INDEX_FILE, 'r', encoding='utf-8') as f:
                    self.cache_sentences = json.load(f)
            except Exception as e:
                print(f"Aviso: No se pudo cargar el índice de caché de audio: {e}")


    def start(self):
        """Inicia el hilo encargado de procesar la cola de audio"""
        """Starts the thread in charge of processing the audio queue"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self.worker_thread.start()

    def stop(self):
        """Detiene el hilo y limpia los recursos"""
        """Stops the thread and cleans the resources"""
        self.running = False
        self.tts_queue.put((None, None)) 
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)

        self._tts_executor.shutdown(wait=False, cancel_futures=True)
        self._offline_executor.shutdown(wait=False, cancel_futures=True)
            
        if pygame.mixer.get_init():
            pygame.mixer.quit()

    def _clear_queue(self):
        """Vacia la cola de audio sin depender de los atributos internos no publicos de Queue"""
        """Empties the audio queue without depending on Queue's non-public internal attributes"""
        while True:
            try:
                self.tts_queue.get_nowait()
            except queue.Empty:
                break

    def _playback_loop(self):
        """Reproduce el audio generado"""
        """Plays the generated audio"""
        while self.running:
            text, force_offline = self.tts_queue.get()
            
            if text is None: 
                self.tts_queue.task_done()
                break
            
            self._process_blocking_voice(text, force_offline)
            self.tts_queue.task_done()

    def _process_blocking_voice(self, text, force_offline=False):
        """Procesa el audio que bloquea a otros audios"""
        """Process the audio that blocks other audios"""
        temp_dir = tempfile.gettempdir()

        if not force_offline:
            if text in self.cache_sentences:
                mp3_file = os.path.join(self.CACHE_DIR, self.cache_sentences[text])
                if os.path.exists(mp3_file):
                    try:
                        if not pygame.mixer.get_init():
                            pygame.mixer.init()
                        pygame.mixer.music.load(mp3_file)
                        pygame.mixer.music.play()
                        esperas = 0
                        while pygame.mixer.music.get_busy() and self.running:
                            time.sleep(0.1)
                            esperas += 1
                        pygame.mixer.music.unload()
                        return
                    except Exception as e:
                        print(f"Fallo al leer caché de audio, pasando a descarga online: {e}")

            mp3_file = os.path.join(temp_dir, f"voz_{uuid.uuid4().hex}.mp3")

            if time.time() >= self._edge_tts_retry_at:
                try:
                    future = self._tts_executor.submit(asyncio.run, self._download_audio(text, mp3_file))
                    future.result(timeout=5.0)
                    pygame.mixer.music.load(mp3_file)
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy() and self.running:
                        time.sleep(0.1)

                    pygame.mixer.music.unload()
                    try: os.remove(mp3_file)
                    except: pass
                    return

                except Exception as e:
                    print(f"Fallo Edge TTS, pasando a voz local. Motivo: {e}")
                    self._edge_tts_retry_at = time.time() + 20.0
                
        try:
            offline_wav = os.path.join(temp_dir, f"voz_offline_{uuid.uuid4().hex}.wav")

            def _generar_wav():
                # Motor NUEVO en cada llamada: reutilizar una misma
                # instancia de pyttsx3 hacia que su segunda llamada a
                # save_to_file se colgase indefinidamente, dejando mudo
                # el hilo de audio entero a partir de ese momento.
                motor = pyttsx3.init()
                motor.setProperty('rate', 160)
                motor.save_to_file(text, offline_wav)
                motor.runAndWait()
                try:
                    motor.stop()
                except Exception:
                    pass

            # Limite duro: si pyttsx3 se cuelga pese a todo, se abandona
            # ese intento y el hilo de audio sigue vivo para las
            # siguientes frases, en vez de quedarse mudo para siempre.
            futuro = self._offline_executor.submit(_generar_wav)
            futuro.result(timeout=15.0)

            existe = os.path.exists(offline_wav)
            tam = os.path.getsize(offline_wav) if existe else 0

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(offline_wav)
            pygame.mixer.music.play()
            esperas = 0
            while pygame.mixer.music.get_busy() and self.running:
                time.sleep(0.1)
                esperas += 1
            pygame.mixer.music.unload()
            try: os.remove(offline_wav)
            except: pass
        except Exception as e_offline:
            print(f"Error crítico en el motor de voz offline: {e_offline}")

    async def _download_audio(self, text, path):
        """Descarga el audio generado"""
        """Downloads the generated audio"""
        communicate = edge_tts.Communicate(text, self.VOICE, rate="+5%")
        await communicate.save(path)

    def read_text(self, text, force_offline=False):
        """Pone el nuevo texto a leer en la cola"""
        """Puts the new text to read in the queue"""
        if not self.running: 
            return
        self.tts_queue.put((text, force_offline))

    def read_text_interrupting(self, text, force_offline=False):
        """Lee textos interrumpiendo el audio previo"""
        """Read texts, interrupting the previous audio"""
        if not self.running: 
            return
            
        self._clear_queue()
            
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            
        self.tts_queue.put((text, force_offline))

    def read_literal_code(self, code, force_offline=False):
        """Lee el codigo literalmente"""
        """Reads code literally"""
        filter_code = strip_static_header(code)
        clean_code = filter_code.replace("*", "todo").replace("(", " paréntesis ").replace(")", "").replace(":", " dos puntos.").replace("_", " ")
        self.read_text(t("code_reading_intro", code=clean_code), force_offline)

    def read_qrs(self, actual_qr_texts):
        """Lee los QRs"""
        """Reads the QRs"""
        qrs_to_read = list(actual_qr_texts)
        
        if not qrs_to_read:
            self.read_text(t("no_blocks_on_table"))
        else:
            positioned_sentences = []
            for index, block in enumerate(qrs_to_read):
                positioned_sentences.append(t("qr_position_item", index=index + 1, block=block))
                
            joined_text = ". ".join(positioned_sentences).replace("_", " ")
            self.read_text(t("qrs_detected_reading", count=len(qrs_to_read), list=joined_text))