import os, time, socket, subprocess, requests
from google import genai
from google.genai import types

class AIManager:
    '''Inicializacion'''
    def __init__(self, api_key, audio_service):
        self.audio_service = audio_service
        self.ollama_process = None  
        if api_key:
            try:
                self.cliente_gemini = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"Aviso: No se pudo iniciar el cliente Gemini: {e}")
                self.cliente_gemini = None
        else:
            print("Aviso: No se proporcionó API Key. Se usará IA local por defecto.")
            self.cliente_gemini = None

    '''Metodo para comprobar la conexion a internet'''
    def _hay_internet(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=1.0)
            self.apagar_ollama()
            return True
        except OSError:
            return False

    '''Metodo para encender la IA local'''
    def encender_ollama(self):
        try:
            # Comprobamos si el puerto ya está escuchando
            requests.get("http://localhost:11434/", timeout=1)
        except requests.ConnectionError:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            self.ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )
            #Damos 2.5 segundos para que el puerto se abra
            time.sleep(2.5)

    '''Metodo para apagar la IA local'''
    def shutdown_ollama(self):
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(
                    ["taskkill", "/F", "/IM", "llama-server.exe"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:  # Linux/Mac
                '''Posibles cambios de nombre, COMPROBAR NOMBRES DE LOS PROCESOS'''
                subprocess.run(["pkill", "-f", "ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["pkill", "-f", "llama-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if self.ollama_process:
                self.ollama_process.wait(timeout=2)
                
        except Exception as e:
            print(f"Aviso al cerrar Ollama: {e}")
        finally:
            self.ollama_process = None

    '''Metodo para eliminar la parte estatica del codigo generada por el propio programa'''
    def _limpiar_codigo(self, codigo_crudo):
        if not codigo_crudo.strip():
            return ""

        lineas = codigo_crudo.split('\n')
        
        leer = False
        lineas_visibles = []
        for linea in enumerate(lineas):
            if leer:
                lineas_visibles.append(linea[1])
            if linea[1] == "# --- Programa Principal ---":
                leer = True
            
        return"\n".join(lineas_visibles)

    '''
        Metodo en en cascada para explicar el codigo
        1. Explica el codigo con Gemini
        2. Si no puede lo explica la IA local
        3. Si falla lee el codigo literalmente
    '''
    def explain_code(self, ruta_codigo, callback_estado):
        try:
            with open(ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
        except FileNotFoundError:
            self.audio_service.read_text("Aún no se ha generado ningún programa.")
            return

        codigo_limpio = self._limpiar_codigo(codigo)
        
        if not codigo_limpio.strip():
            self.audio_service.read_text("El archivo de código está vacío.")
            return

        prompt = f"""Eres un asistente de accesibilidad. Explica en una o dos frases, con lenguaje cotidiano
        y sin usar términos técnicos de programación, puedes especificar que acciones se pueden hacer y
        "cuales son los resultados, qué hace este programa físico:\n\n{codigo_limpio}"""

        sin_internet = not self._hay_internet()

        if not sin_internet and self.cliente_gemini is not None:
            callback_estado("Estado: Conectando con Gemini...", "#8E44AD")
            self.audio_service.read_text("Conectando con Gemini para la explicación de código")
            time.sleep(3)
            try:
                configuracion = types.GenerateContentConfig(max_output_tokens=80, temperature=0.2)
                respuesta = self.cliente_gemini.models.generate_content(
                    model='gemini-flash-lite-latest',
                    contents=prompt,
                    config=configuracion
                )
                callback_estado("Estado: Explicación rápida por Gemini", "#2FA572")
                self.audio_service.read_text(respuesta.text.strip())
                return 
            except Exception as e_gemini:
                print(f"Fallo en Gemini: {e_gemini}")
                callback_estado("Estado: Fallo API Gemini. Iniciando IA local...", "#D4AC0D")
        else:
            # Avisos visuales específicos dependiendo de por qué vamos a local
            if self.cliente_gemini is None:
                callback_estado("Estado: Sin API Key. Iniciando IA local...", "#D4AC0D")
            else:
                callback_estado("Estado: Sin internet. Iniciando IA local...", "#D4AC0D")
        try:
            self.audio_service.read_text("Usando IA local, puede tardar en responder")
            self.encender_ollama()
            
            instrucciones_sistema = (
                "Eres un asistente que explica programas de Micro:bit a personas sin conocimientos técnicos. "
                "Responde SIEMPRE con una sola frase corta. "
                "Menciona siempre la causa física (ej: pulsar botón A, agitar, radio) y el efecto (ej: mostrar corazón, sonido). "
                "Prohibido usar términos de programación y prohibido escribir código."
            )

            respuesta_local = requests.post(
                "http://localhost:11434/api/generate", 
                json={
                    "model": "phi3", 
                    "system": instrucciones_sistema, 
                    "prompt": codigo_limpio,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 80
                    }
                }, 
                timeout=30
            )
            respuesta_local.raise_for_status()
            
            explicacion = respuesta_local.json().get("response", "").strip()
            
            if "```" in explicacion:
                explicacion = explicacion.split("```")[0].strip()
                
            callback_estado("Estado: Explicación por IA Local", "#2FA572")
            self.audio_service.read_text(explicacion, sin_internet)
            return 
            
        except Exception as e_ollama:
            print(f"Fallo en Ollama local: {e_ollama}")

        self.apagar_ollama()
        callback_estado("Estado: IAs no disponibles. Leyendo literalmente.", "#E67E22")
        self.audio_service.read_text("IAs no disponibles. Modo sin conexión. ")
        self.audio_service.leer_codigo_literal(ruta_codigo)