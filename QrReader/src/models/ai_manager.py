import os, time, socket, subprocess, requests
from google import genai
from google.genai import types
from utils.code_text import strip_static_header, strip_tts_wrapper_lines
from utils.strings import t
from utils.app_paths import get_data_dir

class AIManager:
    """Explica el código generado usando Gemini si hay conexión y clave configurada, o una IA local (Ollama) como alternativa sin internet, con lectura literal del código como último recurso"""
    """Explains the generated code using Gemini if there's a connection and a configured key, or a local AI (Ollama) as an alternative without internet, with literal code reading as a last resort"""

    def __init__(self, api_key, audio_service):
        """Guarda el servicio de audio y, si hay clave de Gemini, intenta crear el cliente; sin clave o si falla, se queda listo para usar solo la IA local"""
        """Stores the audio service and, if there's a Gemini key, tries to create the client; without a key or if it fails, it's left ready to use only the local AI"""
        self.audio_service = audio_service
        self.ollama_process = None  
        if api_key:
            try:
                self.gemini_client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"Aviso: No se pudo iniciar el cliente Gemini: {e}")
                self.gemini_client = None
        else:
            print("Aviso: No se proporcionó API Key. Se usará IA local por defecto.")
            self.gemini_client = None

    def _check_internet_and_stop_local_ai(self):
        """Comprueba la conexion a internet; si la hay, apaga la IA local (ya no hace falta, se puede usar Gemini)"""
        """Checks the internet connection; if there is one, shuts down the local AI (no longer needed, Gemini can be used)"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=1.0)
            self.shutdown_ollama()
            return True
        except OSError:
            return False

    def _get_portable_ollama_exe(self):
        """Ruta al ollama portable dentro de la propia carpeta de la app ('ollama'), si existe. La estructura interna del paquete oficial de Ollama difiere segun el sistema operativo -comprobado descargando los tres de verdad-: en Windows el ejecutable esta en la raiz, en Linux dentro de bin/, y el de Mac (una app de escritorio completa) se extrae ya aplanado en el paso de construccion. Se comprueban las rutas posibles en vez de asumir una sola."""
        """Path to the portable ollama inside the app's own folder ('ollama'), if it exists. Ollama's official package internal structure differs by OS -confirmed by actually downloading all three-: on Windows the executable is at the root, on Linux it's inside bin/, and the Mac one (a full desktop app) gets extracted already flattened during the build step. Multiple possible paths are checked instead of assuming just one."""
        base = os.path.join(get_data_dir(), "ollama")
        candidates = [
            os.path.join(base, "ollama.exe"),     # Windows
            os.path.join(base, "bin", "ollama"),  # Linux (estructura real del .tar.zst oficial)
            os.path.join(base, "ollama"),         # Mac (aplanado desde Contents/Resources/ollama en el build)
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    def _start_ollama(self):
        """Metodo para encender la IA local"""
        """Method to initiate the local AI"""
        try:
            requests.get("http://localhost:11434/", timeout=1)
        except requests.ConnectionError:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

            portable_exe = self._get_portable_ollama_exe()
            ollama_cmd = portable_exe if portable_exe else "ollama"

            env = os.environ.copy()
            models_dir = os.path.join(get_data_dir(), "ollama_models")
            os.makedirs(models_dir, exist_ok=True)
            env["OLLAMA_MODELS"] = models_dir

            try:
                self.ollama_process = subprocess.Popen(
                    [ollama_cmd, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    env=env,
                )
                time.sleep(2.5)
            except FileNotFoundError:
                print("Aviso: no se encuentra Ollama (ni portable en la carpeta 'ollama', ni instalado en el sistema).")

    def shutdown_ollama(self):
        """Lanza el cierre del proceso que sirve el modelo y del propio demonio de Ollama, sin esperar a que terminen"""
        """Fires off closing the process serving the model and the Ollama daemon itself, without waiting for them to finish"""
        def _fire_and_forget(cmd):
            """Lanza el comando de cierre como proceso independiente, sin esperar a que termine ni comprobar su resultado"""
            """Launches the shutdown command as an independent process, without waiting for it to finish or checking its result"""
            try:
                flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW) if os.name == 'nt' else 0
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            except Exception as e:
                print(f"Aviso al lanzar el cierre de Ollama: {e}")

        if os.name == 'nt':  # Windows
            _fire_and_forget(["taskkill", "/F", "/FI", "IMAGENAME eq *llama*", "/IM", "*"])
            _fire_and_forget(["taskkill", "/F", "/IM", "llama-server.exe"])  # respaldo directo, por si el filtro fallara
            _fire_and_forget(["taskkill", "/F", "/IM", "ollama.exe"])  # respaldo directo, por si el filtro fallara
        else:  # Linux/Mac
            _fire_and_forget(["pkill", "-f", "llama"])
            _fire_and_forget(["pkill", "-f", "ollama"])
            
        self.ollama_process = None

    def explain_code(self, code, callback_state):
        """
            Metodo en cascada para explicar el codigo
            1. Explica el codigo con Gemini
            2. Si no puede lo explica la IA local
            3. Si falla lee el codigo literalmente
        """
        """
            Method on cascade to explain the code
            1. Explain the code with gemini
            2. If not possible the local AI explains it
            3. If it fails reads the code literally
        """

        clean_code = strip_static_header(code)
        clean_code = strip_tts_wrapper_lines(clean_code)
        
        if not clean_code.strip():
            self.audio_service.read_text(t("code_empty"))
            return

        prompt = t("gemini_prompt", code=clean_code)

        has_internet = self._check_internet_and_stop_local_ai()

        if has_internet and self.gemini_client is not None:
            callback_state(t("status_connecting_gemini"), "#8E44AD")
            self.audio_service.read_text(t("connecting_gemini_audio"))
            time.sleep(3)
            try:
                config = types.GenerateContentConfig(max_output_tokens=80, temperature=0.2)
                answer = self.gemini_client.models.generate_content(
                    model='gemini-flash-lite-latest',
                    contents=prompt,
                    config=config
                )
                callback_state(t("status_gemini_explained"), "#2FA572")
                self.audio_service.read_text(answer.text.strip())
                return 
            except Exception as e_gemini:
                print(f"Fallo en Gemini: {e_gemini}")
                callback_state(t("status_gemini_failed"), "#D4AC0D")
        else:
            if self.gemini_client is None:
                callback_state(t("status_no_api_key"), "#D4AC0D")
            else:
                callback_state(t("status_no_internet"), "#D4AC0D")
        try:
            self.audio_service.read_text(t("using_local_ai"))
            self._start_ollama()
            
            system_instructions = t("ollama_system_instructions")

            local_answer = requests.post(
                "http://localhost:11434/api/generate", 
                json={
                    "model": "phi3", 
                    "system": system_instructions, 
                    "prompt": clean_code,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 80
                    }
                }, 
                timeout=30
            )
            local_answer.raise_for_status()
            
            explanation = local_answer.json().get("response", "").strip()
            
            if "```" in explanation:
                explanation = explanation.split("```")[0].strip()
                
            callback_state(t("status_local_explained"), "#2FA572")
            self.audio_service.read_text(explanation, not has_internet)
            return 
            
        except Exception as e_ollama:
            print(f"Fallo en Ollama local: {e_ollama}")

        self.shutdown_ollama()
        callback_state(t("status_ai_unavailable"), "#E67E22")
        self.audio_service.read_text(t("ai_unavailable_audio"))
        self.audio_service.read_literal_code(code)