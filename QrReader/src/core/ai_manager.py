import os
import time
import socket
import subprocess
import requests
from google import genai
from google.genai import types
from core.audio import GestorVoz

class AIManager:
    """Motor encargado de procesar el código y generar explicaciones mediante IA."""
    
    def __init__(self, api_key):
        self.cliente_gemini = genai.Client(api_key=api_key)
        self.ollama_process = None  # Variable para controlar el servidor local

    def _hay_internet(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=1.0)
            return True
        except OSError:
            return False

    def encender_ollama(self):
        try:
            # Comprobamos si el puerto ya está escuchando
            requests.get("http://localhost:11434/", timeout=1)
        except requests.ConnectionError:
            print("Ollama apagado. Encendiendo servidor local en segundo plano...")
            # Ocultamos la consola negra en Windows
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            self.ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )
            # Damos 2.5 segundos de margen para que el puerto se abra correctamente
            time.sleep(2.5)
            print("Servidor Ollama iniciado con éxito.")

    def apagar_ollama(self):
        print("Apagando servidor local de IA y purgando la memoria RAM...")
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(
                    ["taskkill", "/F", "/IM", "llama-server.exe"], # Por si la versión de Ollama usa este nombre
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
            print("Ollama apagado al 100%. RAM completamente liberada.")

    def _limpiar_codigo(self, codigo_crudo):
        """Filtra los pitidos de inicialización para no confundir a la IA."""
        if not codigo_crudo.strip():
            return ""

        lineas = codigo_crudo.split('\n')
        idx_ultimo_pitch = -1
        
        for i, linea in enumerate(lineas):
            if "music.pitch" in linea:
                idx_ultimo_pitch = i
            if linea.startswith("while ") or linea.startswith("if ") or linea.startswith("def "):
                break

        if idx_ultimo_pitch != -1:
            lineas_visibles = []
            for i, linea in enumerate(lineas):
                if i <= idx_ultimo_pitch:
                    if linea.startswith("import ") or linea.startswith("from "):
                        lineas_visibles.append(linea)
                else:
                    lineas_visibles.append(linea)
            return "\n".join(lineas_visibles)
        
        return codigo_crudo

    def explicar_codigo(self, ruta_codigo, callback_estado):
        """
        Ejecuta la IA en cascada.
        :param ruta_codigo: Ruta del archivo Python a analizar.
        :param callback_estado: Función para enviar actualizaciones a la interfaz visual.
        """
        try:
            with open(ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
        except FileNotFoundError:
            GestorVoz.leer_texto("Aún no se ha generado ningún programa.")
            return

        codigo_limpio = self._limpiar_codigo(codigo)
        
        if not codigo_limpio.strip():
            GestorVoz.leer_texto("El archivo de código está vacío.")
            return

        prompt = f"Eres un asistente de accesibilidad. Explica en una o dos frases, con lenguaje cotidiano y sin usar términos técnicos de programación, qué hace este programa físico:\n\n{codigo_limpio}"

        # 1. Comprobar internet de forma ultrarrápida
        sin_internet = not self._hay_internet()

        # 2. NIVEL 1: LA NUBE (Gemini API)
        if not sin_internet:
            self.apagar_ollama()
            callback_estado("Estado: Conectando con Gemini...", "#8E44AD")
            try:
                configuracion = types.GenerateContentConfig(max_output_tokens=80, temperature=0.2)
                respuesta = self.cliente_gemini.models.generate_content(
                    model='gemini-flash-lite-latest',
                    contents=prompt,
                    config=configuracion
                )
                callback_estado("Estado: Explicación rápida por Gemini", "#2FA572")
                GestorVoz.leer_texto(respuesta.text.strip())
                return 
            except Exception as e_gemini:
                print(f"Fallo en Gemini: {e_gemini}")
                callback_estado("Estado: Fallo API Gemini. Iniciando IA local...", "#D4AC0D")
        else:
            callback_estado("Estado: Sin internet. Iniciando IA local...", "#D4AC0D")

        # 3. NIVEL 2: MOTOR LOCAL (Ollama)
        try:
            self.encender_ollama()
            
            # 1. EL SUBCONSCIENTE (Reglas estrictas separadas del código)
            instrucciones_sistema = (
                "Eres un asistente que explica programas de Micro:bit a personas sin conocimientos técnicos. "
                "Responde SIEMPRE con una sola frase corta. "
                "Menciona siempre la causa física (ej: pulsar botón A, agitar, radio) y el efecto (ej: mostrar corazón, sonido). "
                "Prohibido usar términos de programación y prohibido escribir código."
            )
            
            # 2. LA PETICIÓN SEPARADA
            respuesta_local = requests.post(
                "http://localhost:11434/api/generate", 
                json={
                    "model": "phi3", 
                    "system": instrucciones_sistema,  # <--- Inyectamos las reglas aquí
                    "prompt": codigo_limpio,          # <--- La IA solo ve el código aquí
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 80
                    }
                }, 
                timeout=15 
            )
            respuesta_local.raise_for_status()
            
            explicacion = respuesta_local.json().get("response", "").strip()
            
            # 3. FILTRO POST-PROCESADO
            if "```" in explicacion:
                explicacion = explicacion.split("```")[0].strip()
                
            callback_estado("Estado: Explicación por IA Local", "#2FA572")
            GestorVoz.leer_texto(explicacion, sin_internet)
            return 
            
        except Exception as e_ollama:
            print(f"Fallo en Ollama local: {e_ollama}")

        # 4. NIVEL 3: FALLBACK ABSOLUTO (Lectura Literal)
        callback_estado("Estado: IAs no disponibles. Leyendo literalmente.", "#E67E22")
        GestorVoz.leer_texto("Modo sin conexión. ")
        GestorVoz.leer_codigo_literal(ruta_codigo)