import os, asyncio, threading, uuid, tempfile, edge_tts, pygame, pyttsx3, queue, time, json

class AudioService:
    def __init__(self):
        self.VOICE = "es-ES-ElviraNeural" 
        
        # Inicialización del mixer para su propia instancia
        pygame.mixer.init()
        self.cola_tts = queue.Queue()
        self.corriendo = False
        self.hilo_worker = None
        
        self.BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.CACHE_DIR = os.path.join(self.BASE_DIR, 'data', 'assets', 'audio_cache')
        self.INDEX_FILE = os.path.join(self.CACHE_DIR, 'index.json')
        
        self.cache_frases = {}
        if os.path.exists(self.INDEX_FILE):
            try:
                with open(self.INDEX_FILE, 'r', encoding='utf-8') as f:
                    self.cache_frases = json.load(f)
            except Exception as e:
                print(f"Aviso: No se pudo cargar el índice de caché de audio: {e}")

    # --- CONTROL DEL CICLO DE VIDA ---

    def iniciar(self):
        """Inicia el hilo trabajador encargado de procesar la cola de audio."""
        if not self.corriendo:
            self.corriendo = True
            self.hilo_worker = threading.Thread(target=self._bucle_reproduccion, daemon=True)
            self.hilo_worker.start()

    def stop(self):
        """Detiene el hilo trabajador y limpia los recursos."""
        self.corriendo = False
        # Metemos un elemento vacío (None) para desbloquear la cola si está vacía y esperando
        self.cola_tts.put((None, None)) 
        
        if self.hilo_worker and self.hilo_worker.is_alive():
            self.hilo_worker.join(timeout=1.0)
            
        if pygame.mixer.get_init():
            pygame.mixer.quit()

    # --- LÓGICA INTERNA DE REPRODUCCIÓN ---

    def _bucle_reproduccion(self):
        while self.corriendo:
            texto, sin_internet = self.cola_tts.get()
            
            # Condición de salida limpia
            if texto is None: 
                self.cola_tts.task_done()
                break
                
            self._procesar_voz_bloqueante(texto, sin_internet)
            self.cola_tts.task_done()

    def _procesar_voz_bloqueante(self, texto, sin_internet=False):
        if not sin_internet:
            # 1. Intentar cargar desde Caché
            if texto in self.cache_frases:
                archivo_mp3 = os.path.join(self.CACHE_DIR, self.cache_frases[texto])
                if os.path.exists(archivo_mp3):
                    try:
                        pygame.mixer.music.load(archivo_mp3)
                        pygame.mixer.music.play()
                        # Comprobamos también self.corriendo para poder interrumpir al cerrar el programa
                        while pygame.mixer.music.get_busy() and self.corriendo:
                            time.sleep(0.1)
                        pygame.mixer.music.unload()
                        return
                    except Exception as e:
                        print(f"Fallo al leer caché de audio, pasando a descarga online: {e}")

            # 2. Descarga dinámica con Edge TTS
            temp_dir = tempfile.gettempdir()
            archivo_mp3 = os.path.join(temp_dir, f"voz_{uuid.uuid4().hex}.mp3")

            try:
                asyncio.run(self._descargar_audio(texto, archivo_mp3))
                pygame.mixer.music.load(archivo_mp3)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy() and self.corriendo:
                    time.sleep(0.1)
                    
                pygame.mixer.music.unload()
                try: os.remove(archivo_mp3) 
                except: pass
                return
                
            except Exception as e:
                print(f"Fallo Edge TTS, pasando a voz local. Motivo: {e}")
                
        # 3. Fallback: Motor de Voz Offline (pyttsx3)
        try:
            motor_offline = pyttsx3.init()
            motor_offline.setProperty('rate', 160) 
            motor_offline.say(texto)
            motor_offline.runAndWait()
        except Exception as e_offline:
            print(f"Error crítico en el motor de voz offline: {e_offline}")

    async def _descargar_audio(self, texto, ruta):
        communicate = edge_tts.Communicate(texto, self.VOICE, rate="+5%")
        await communicate.save(ruta)

    # --- MÉTODOS PÚBLICOS DE INSERCIÓN EN COLA ---

    def read_text(self, texto, sin_internet=False):
        if not self.corriendo: 
            return
        self.cola_tts.put((texto, sin_internet))

    def read_text_interrupting(self, texto, sin_internet=False):
        if not self.corriendo: 
            return
            
        # Vaciamos la cola actual
        with self.cola_tts.mutex:
            self.cola_tts.queue.clear()
            
        # Detenemos el audio en curso si existe
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            
        self.cola_tts.put((texto, sin_internet))

    def read_literal_code(self, ruta_codigo, sin_internet=False):
        try:
            with open(ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
            
            lineas = codigo.split('\n')
            leer = False
            lineas_visibles = []
            
            for linea in lineas:
                if leer:
                    lineas_visibles.append(linea)
                if linea == "# --- Programa Principal ---":
                    leer = True
                
            codigo_filtrado = "\n".join(lineas_visibles)
            codigo_limpio = codigo_filtrado.replace("*", "todo").replace("(", " paréntesis ").replace(")", "").replace(":", " dos puntos.")
            self.read_text(f"El programa actual es el siguiente... {codigo_limpio}", sin_internet)
            
        except FileNotFoundError:
            self.read_text("Aún no se ha generado ningún código.", sin_internet)

    def read_qrs(self, textos_qr_actuales):
        qrs_a_leer = list(textos_qr_actuales)
        
        if not qrs_a_leer:
            self.read_text("No detecto ningún bloque en la mesa.")
        else:
            frases_posicionadas = []
            for indice, bloque in enumerate(qrs_a_leer):
                frases_posicionadas.append(f"posición {indice + 1}, {bloque}")
                
            texto_unido = ". ".join(frases_posicionadas).replace("_", " ")
            self.read_text(f"Detectados {len(qrs_a_leer)} bloques. Leyendo de arriba a abajo... {texto_unido}.")