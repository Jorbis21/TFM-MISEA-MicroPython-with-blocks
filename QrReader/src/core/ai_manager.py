import requests
from google import genai
from google.genai import types
from core.audio import GestorVoz

class AIManager:
    """Motor encargado de procesar el código y generar explicaciones mediante IA."""
    
    def __init__(self, api_key):
        self.cliente_gemini = genai.Client(api_key=api_key)

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

        # 1. Comprobar internet de forma rápida
        sin_internet = False
        try:
            requests.get("https://www.google.com", timeout=2)
        except requests.RequestException:
            sin_internet = True

        # 2. NIVEL 1: LA NUBE (Gemini API)
        if not sin_internet:
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
                callback_estado("Estado: Sin internet o fallo API. Iniciando IA local...", "#D4AC0D")

        # 3. NIVEL 2: MOTOR LOCAL (Ollama)
        callback_estado("Estado: Usando IA Local...", "#D4AC0D")
        try:
            respuesta_local = requests.post(
                "http://localhost:11434/api/generate", 
                json={"model": "qwen2.5:1.5b", "prompt": prompt, "stream": False}, 
                timeout=4
            )
            respuesta_local.raise_for_status()
            
            explicacion = respuesta_local.json().get("response", "").strip()
            callback_estado("Estado: Explicación por IA Local", "#2FA572")
            GestorVoz.leer_texto(explicacion, sin_internet)
            return 
        except Exception as e_ollama:
            print(f"Fallo en Ollama local: {e_ollama}")

        # 4. NIVEL 3: FALLBACK ABSOLUTO (Lectura Literal)
        callback_estado("Estado: IAs no disponibles. Leyendo literalmente.", "#E67E22")
        GestorVoz.leer_texto("Modo sin conexión. ")
        GestorVoz.leer_codigo_literal(ruta_codigo)