import os, time, socket, subprocess, requests
from google import genai
from google.genai import types
from utils.code_text import strip_static_header, strip_tts_wrapper_lines
from utils.strings import t
from utils.app_paths import get_data_dir

class AIManager:

    def __init__(self, api_key, audio_service):
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

            # Prioridad: el ollama portable que viaja dentro de la carpeta de
            # la app (carpeta "ollama", ver Instalar_IA_Local.bat). Si no
            # existe, se prueba con un "ollama" instalado en el sistema, por
            # si alguien lo tiene asi en vez de portable.
            # Priority: the portable ollama that ships inside the app's own
            # folder ("ollama" folder, see Instalar_IA_Local.bat). If it
            # doesn't exist, falls back to a system-installed "ollama", in
            # case someone has it that way instead of portable.
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
            # subprocess.Popen (no .run) y sin esperar: un proceso con un
            # modelo grande cargado en RAM puede tardar mas de lo que
            # cualquier timeout razonable permitiria en morir del todo, ni
            # siquiera con /F. Esperar aqui, aunque fuera con un limite,
            # tiene un problema real: si el limite se agota, Python no se
            # limita a dejar de esperar - MATA al propio taskkill a medias,
            # dejando el proceso objetivo sin terminar de matar. En Windows,
            # DETACHED_PROCESS desliga el taskkill de QrReader por completo,
            # así que sigue vivo y termina su trabajo aunque QrReader ya se
            # haya cerrado del todo.
            # subprocess.Popen (not .run) and without waiting: a process with
            # a large model loaded in RAM can take longer to fully die than
            # any reasonable timeout would allow, even with /F. Waiting here,
            # even with a limit, has a real problem: if the limit runs out,
            # Python doesn't just stop waiting - it KILLS taskkill itself
            # partway through, leaving the target process not fully killed.
            # On Windows, DETACHED_PROCESS fully unlinks taskkill from
            # QrReader, so it stays alive and finishes its job even after
            # QrReader itself has completely closed.
            try:
                flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW) if os.name == 'nt' else 0
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            except Exception as e:
                print(f"Aviso al lanzar el cierre de Ollama: {e}")

        if os.name == 'nt':  # Windows
            # Comodin amplio en vez de un nombre exacto: el proceso que sirve
            # el modelo ha tenido nombres distintos segun la version/build de
            # Ollama - confirmado "llama-server.exe" en la practica (este es
            # el que consume la RAM) y "ollama_llama_server.exe" en su propio
            # repositorio de GitHub. "*llama*" (con comodin a los dos lados,
            # no solo de prefijo) engancha los dos; las otras dos lineas son
            # respaldo directo por si el filtro fallara. El comodin en /IM
            # solo funciona junto con un filtro /FI, de ahi la sintaxis con
            # /FI e /IM *.
            # Broad wildcard instead of an exact name: the process serving
            # the model has had different names depending on the Ollama
            # version/build - confirmed "llama-server.exe" in practice (this
            # is the one eating RAM) and "ollama_llama_server.exe" on their
            # own GitHub repo. "*llama*" (wildcard on both sides, not just a
            # prefix) catches both; the other two lines are a direct backup
            # in case the filter fails. The wildcard on /IM only works
            # together with a /FI filter, hence the syntax with /FI and /IM *.
            _fire_and_forget(["taskkill", "/F", "/FI", "IMAGENAME eq *llama*", "/IM", "*"])
            _fire_and_forget(["taskkill", "/F", "/IM", "llama-server.exe"])  # respaldo directo, por si el filtro fallara
            _fire_and_forget(["taskkill", "/F", "/IM", "ollama.exe"])  # respaldo directo, por si el filtro fallara
        else:  # Linux/Mac
            _fire_and_forget(["pkill", "-f", "llama"])
            _fire_and_forget(["pkill", "-f", "ollama"])

        # Ya no se espera a self.ollama_process: los taskkill/pkill de arriba
        # se encargan de matarlo igual, y ahora son independientes de este
        # proceso - esperar aqui ya no aporta nada y solo reintroduciria el
        # mismo problema de bloqueo.
        # self.ollama_process is no longer waited on: the taskkill/pkill
        # calls above kill it just the same, and are now independent of this
        # process - waiting here wouldn't add anything and would only
        # reintroduce the same blocking problem.
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