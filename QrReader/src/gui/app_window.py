import os
import re
import threading
import requests
import customtkinter as ctk

# --- NUEVOS IMPORTS DEL SDK ---
from google import genai
from google.genai import types
# ------------------------------

from PIL import Image
from core.vision import VisionEngine
from core.audio import GestorVoz
from core.translator import MicrobitTranslator

# === CONFIGURACIÓN DE GEMINI (NUEVO SDK) ===
cliente_gemini = genai.Client(api_key="AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w")
# ===============================

class AppCamara(ctk.CTk):
    def __init__(self, workspace_dir, config_dir):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.ruta_img = os.path.join(self.workspace_dir, "inputs", "program.jpg")
        self.ruta_codigo = os.path.join(self.workspace_dir, "outputs", "MicroBit_Code.py")
        
        self.textos_qr_actuales = []
        self.title("Analizador de Cámara USB")
        self.geometry("1920x1080") 
        
        self.vision = VisionEngine()

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=0) 
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(self, corner_radius=0)
        self.sidebar.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="CONTROLES", font=ctk.CTkFont(size=15, weight="bold"))
        self.logo_label.pack(padx=5, pady=(5, 2))

        self.frame_botones = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_botones.pack(pady=5, fill="x", padx=5)

        # Ajustamos los anchos a 140-150 para que quepan todos los botones en la misma línea
        self.btn_capturar = ctk.CTkButton(
            self.frame_botones, text="Tomar Foto", command=self.accion_capturar,
            width=140, height=45, corner_radius=8,
            fg_color="#0052cc", hover_color="#003d99", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_capturar.pack(padx=3, pady=2, side="left", expand=True)
        
        self.btn_enviar = ctk.CTkButton(
            self.frame_botones, text="Enviar a MicroBit", command=self.accion_enviar,
            width=140, height=45, corner_radius=8,
            fg_color="#2FA572", hover_color="#106A43", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_enviar.pack(padx=3, pady=2, side="left", expand=True)

        self.btn_leer = ctk.CTkButton(
            self.frame_botones, text="Leer Literal", command=self.accion_leer_codigo,
            width=140, height=45, corner_radius=8,
            fg_color="#E67E22", hover_color="#D35400", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_leer.pack(padx=3, pady=2, side="left", expand=True)

        self.btn_ia = ctk.CTkButton(
            self.frame_botones, text="Explicar con IA", command=self.accion_explicar_ia,
            width=140, height=45, corner_radius=8,
            fg_color="#8E44AD", hover_color="#732D91", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_ia.pack(padx=3, pady=2, side="left", expand=True)

        self.btn_leer_qrs = ctk.CTkButton(
            self.frame_botones, text="Leer QRs Mesa", command=self.accion_leer_qrs_pantalla,
            width=140, height=45, corner_radius=8,
            fg_color="#4A235A", hover_color="#5B2C6F", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_leer_qrs.pack(padx=3, pady=2, side="left", expand=True)

        self.modo_edicion = False
        
        self.btn_editar = ctk.CTkButton(
            self.frame_botones, text="Editar Código", command=self.accion_editar_codigo,
            width=140, height=45, corner_radius=8,
            fg_color="#D4AC0D", hover_color="#B9770E", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_editar.pack(padx=3, pady=2, side="left", expand=True)

        self.status_label = ctk.CTkLabel(self.sidebar, text="Estado: Cámara Activa", text_color="gray")
        self.status_label.pack(side="bottom", pady=5)
        
        self.contenedor_visor = ctk.CTkFrame(self)
        self.contenedor_visor.grid(row=0, column=1, rowspan=2, padx=(5, 2), pady=5, sticky="nsew")
        self.video_label = ctk.CTkLabel(self.contenedor_visor, text="")
        self.video_label.pack(expand=True, fill="both")

        # --- ÁREA DE CÓDIGO (ESTILO VS CODE) ---
        self.contenedor_codigo = ctk.CTkFrame(self, fg_color="#1E1E1E") 
        self.contenedor_codigo.grid(row=1, column=0, padx=(10, 20), pady=20, sticky="nsew")
        self.contenedor_codigo.grid_columnconfigure(1, weight=1)
        self.contenedor_codigo.grid_rowconfigure(0, weight=1)

        self.caja_lineas = ctk.CTkTextbox(
            self.contenedor_codigo, width=45, fg_color="#1E1E1E", text_color="#858585", 
            font=ctk.CTkFont(family="Consolas", size=14), wrap="none"
        )
        self.caja_lineas.grid(row=0, column=0, sticky="ns", padx=(5, 0), pady=15)

        self.caja_texto = ctk.CTkTextbox(
            self.contenedor_codigo, fg_color="#1E1E1E", text_color="#D4D4D4", 
            font=ctk.CTkFont(family="Consolas", size=14), wrap="none"
        )
        self.caja_texto.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=15)

        # --- DICCIONARIO DE COLORES (VS Code Dark+ Theme) ---
        self.caja_texto.tag_config("keyword", foreground="#569CD6") 
        self.caja_texto.tag_config("flow", foreground="#C586C0")    
        self.caja_texto.tag_config("function", foreground="#DCDCAA")
        self.caja_texto.tag_config("string", foreground="#CE9178")  
        self.caja_texto.tag_config("number", foreground="#B5CEA8")  
        self.caja_texto.tag_config("comment", foreground="#6A9955") 
        self.caja_texto.tag_config("boolean", foreground="#569CD6") 
        self.caja_texto.tag_config("error", background="#4D0000", foreground="#FFB3B3", underline=True)
        # ---------------------------------------------------

        self.leer_codigo_generado()
        self.actualizar_frame()
        self.traductor = MicrobitTranslator(config_dir=config_dir)

        # Atajos de teclado para guardar
        self.bind("<Control-s>", self.accion_atajo_guardar)
        self.bind("<Command-s>", self.accion_atajo_guardar)

    def actualizar_frame(self):
        frame_bgr, frame_rgb, textos = self.vision.markElems()
        
        if frame_rgb is not None:
            self.frame_actual_bgr = frame_bgr
            self.textos_qr_actuales = textos
            
            img_pil = Image.fromarray(frame_rgb)
            img_tk = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(540, 960))
            self.video_label.configure(image=img_tk)
            self.video_label.image = img_tk

        self.after(15, self.actualizar_frame)

    def accion_capturar(self):
        if hasattr(self, 'frame_actual_bgr'):
            self.vision.takePhoto(self.frame_actual_bgr, self.ruta_img)
            matriz_espacial = self.vision.get_command_matrix()
            self.traductor.generar_codigo(matriz_espacial, self.ruta_codigo) 
            self.leer_codigo_generado()

    def accion_enviar(self):
        self.traductor.subir(self.ruta_codigo)

    def accion_leer_codigo(self):
        try:
            with open(self.ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
            codigo_limpio = codigo.replace("*", "todo").replace("(", " paréntesis ").replace(")", "").replace(":", " dos puntos.")
            GestorVoz.leer_texto(f"El programa actual es el siguiente... {codigo_limpio}")
        except FileNotFoundError:
            GestorVoz.leer_texto("Aún no se ha generado ningún código.")

    def accion_leer_qrs_pantalla(self):
        qrs_a_leer = list(self.textos_qr_actuales)
        if not qrs_a_leer:
            GestorVoz.leer_texto("No detecto ningún bloque en la mesa.")
        else:
            texto_unido = ". ".join(qrs_a_leer).replace("_", " ")
            GestorVoz.leer_texto(f"Detectados {len(qrs_a_leer)} bloques. Leyendo de arriba a abajo: {texto_unido}")

    # =========================================================
    # MOTOR DE EXPLICACIÓN IA (3 NIVELES DE CASCADA)
    # =========================================================
    def accion_explicar_ia(self):
        hilo = threading.Thread(target=self._tarea_explicar_ia)
        hilo.start()

    def _tarea_explicar_ia(self):
        try:
            sin_internet = False
            try:
                requests.get("https://www.google.com", timeout=2)
            except:
                sin_internet = True

            with open(self.ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
                
            if not codigo.strip():
                GestorVoz.leer_texto("El archivo de código está vacío.")
                return

            # --- FILTRO PARA OCULTAR PITCHES A LA IA ---
            lineas = codigo.split('\n')
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
                codigo_limpio = "\n".join(lineas_visibles)
            else:
                codigo_limpio = codigo
            # -------------------------------------------

            prompt = f"Eres un asistente de accesibilidad. Explica en una o dos frases, con lenguaje cotidiano y sin usar términos técnicos de programación (no digas variables, bucles, if, ni código), qué hace este programa físico:\n\n{codigo_limpio}"

            # NIVEL 1: LA NUBE (Gemini API - NUEVO SDK)
            if not sin_internet:
                self.status_label.configure(text="Estado: Conectando con Gemini...", text_color="#8E44AD")
                try:
                    # La nueva forma de pasar parámetros de generación
                    configuracion = types.GenerateContentConfig(
                        max_output_tokens=80,
                        temperature=0.2
                    )
                    
                    # Usamos el cliente directamente en lugar de instanciar un modelo previo
                    respuesta = cliente_gemini.models.generate_content(
                        model='gemini-flash-lite-latest',
                        contents=prompt,
                        config=configuracion
                    )
                    explicacion = respuesta.text.strip()
                    
                    self.status_label.configure(text="Estado: Explicación rápida por Gemini", text_color="#2FA572")
                    GestorVoz.leer_texto(explicacion)
                    return 
                except Exception as e_gemini:
                    print(f"Fallo en Gemini: {e_gemini}")
                    self.status_label.configure(text="Estado: Sin internet o fallo API. Iniciando IA local...", text_color="#D4AC0D")

            # NIVEL 2: MOTOR LOCAL (Ollama con Qwen 2.5 1.5B)
            self.status_label.configure(text="Estado: Usando IA Local...", text_color="#D4AC0D")
            try:
                url = "http://localhost:11434/api/generate"
                payload = {
                    "model": "qwen2.5:1.5b", 
                    "prompt": prompt,
                    "stream": False
                }
                respuesta_local = requests.post(url, json=payload, timeout=4)
                respuesta_local.raise_for_status()
                
                explicacion = respuesta_local.json().get("response", "").strip()
                self.status_label.configure(text="Estado: Explicación por IA Local", text_color="#2FA572")
                GestorVoz.leer_texto(explicacion, sin_internet)
                return 
            except Exception as e_ollama:
                print(f"Fallo en Ollama local: {e_ollama}")

            # NIVEL 3: FALLBACK ABSOLUTO (Lectura Literal)
            self.status_label.configure(text="Estado: IAs no disponibles. Leyendo literalmente.", text_color="#E67E22")
            GestorVoz.leer_texto("Modo sin conexión. ")
            self.accion_leer_codigo()

        except FileNotFoundError:
            GestorVoz.leer_texto("Aún no se ha generado ningún programa para que lo analice.")
        except Exception as e:
            self.status_label.configure(text="Estado: Error general en el análisis", text_color="#FF4C4C")
            print(f"Error general IA: {e}")

    def leer_codigo_generado(self):
        self.caja_texto.configure(state="normal")
        self.caja_lineas.configure(state="normal")
        self.caja_texto.delete("1.0", "end")
        self.caja_lineas.delete("1.0", "end")

        try:
            with open(self.ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
            
            # Filtro inteligente de pitidos de inicialización
            lineas = codigo.split('\n')
            idx_ultimo_pitch = -1
            
            for i, linea in enumerate(lineas):
                if "music.pitch" in linea:
                    idx_ultimo_pitch = i
                if linea.startswith("while ") or linea.startswith("if ") or linea.startswith("def "):
                    break

            if idx_ultimo_pitch != -1:
                lineas_visibles = []
                self.bloque_pitches = [] 
                
                for i, linea in enumerate(lineas):
                    if i <= idx_ultimo_pitch:
                        if linea.startswith("import ") or linea.startswith("from "):
                            lineas_visibles.append(linea)
                        elif "music.pitch" in linea:
                            self.bloque_pitches.append(linea)
                    else:
                        if i == idx_ultimo_pitch + 1 and linea.strip() == "" and lineas_visibles and lineas_visibles[-1].strip() == "":
                            continue
                        lineas_visibles.append(linea)
                        
                codigo_mostrar = "\n".join(lineas_visibles)
            else:
                self.bloque_pitches = []
                codigo_mostrar = codigo

            lineas_ui = codigo_mostrar.split('\n')
            nums = "\n".join(str(i) for i in range(1, len(lineas_ui) + 1))
            
            self.caja_lineas.insert("1.0", nums)
            self.caja_texto.insert("1.0", codigo_mostrar)

            patrones = {
                "flow": r'\b(if|elif|else|while|for|in|break|continue|return)\b',
                "keyword": r'\b(from|import|def|class|pass|global|as)\b',
                "boolean": r'\b(True|False|None)\b',
                "function": r'\b([a-zA-Z_]\w*)(?=\()',  
                "number": r'\b(\d+\.?\d*)\b',
                "string": r'(".*?"|\'.*?\')',           
                "comment": r'(#.*)'                     
            }

            for tag, patron in patrones.items():
                for index, linea in enumerate(lineas_ui):
                    for match in re.finditer(patron, linea):
                        start, end = match.span()
                        self.caja_texto.tag_add(tag, f"{index+1}.{start}", f"{index+1}.{end}")

            try:
                compile(codigo_mostrar, '<string>', 'exec')
                self.status_label.configure(text="Estado: Código sin errores", text_color="#2FA572")
                
            except SyntaxError as e:
                linea_err = e.lineno
                col_err = (e.offset - 1) if e.offset is not None else 0
                
                self.caja_texto.tag_add("error", f"{linea_err}.{col_err}", f"{linea_err}.end")
                
                motivo = "Error de Identación" if "indent" in e.msg.lower() else "Error de Sintaxis"
                self.status_label.configure(text=f"Línea {linea_err} | {motivo}: {e.msg}", text_color="#FF4C4C")

                mensaje_voz = f"Atención. Hay un {motivo.lower()} en la línea {linea_err}."
                GestorVoz.leer_texto(mensaje_voz)

        except FileNotFoundError:
            self.caja_texto.insert("1.0", "# Archivo no generado.")
            self.caja_lineas.insert("1.0", "1")
            self.status_label.configure(text="Estado: Esperando captura...", text_color="gray")

        self.caja_texto.configure(state="disabled")
        self.caja_lineas.configure(state="disabled")

    def _guardar_codigo_archivo(self):
        nuevo_codigo = self.caja_texto.get("1.0", "end-1c")
        
        # Reinyección automática de los pitidos ocultos
        if hasattr(self, 'bloque_pitches') and self.bloque_pitches:
            lineas_editadas = nuevo_codigo.split('\n')
            idx_insert = 0
            
            for i, linea in enumerate(lineas_editadas):
                if linea.startswith("import ") or linea.startswith("from ") or linea.strip() == "":
                    idx_insert = i + 1
                else:
                    break
            
            if idx_insert < len(lineas_editadas) and lineas_editadas[idx_insert].strip() != "":
                lineas_finales = lineas_editadas[:idx_insert] + self.bloque_pitches + [""] + lineas_editadas[idx_insert:]
            else:
                lineas_finales = lineas_editadas[:idx_insert] + self.bloque_pitches + lineas_editadas[idx_insert:]
                
            codigo_a_guardar = "\n".join(lineas_finales)
        else:
            codigo_a_guardar = nuevo_codigo
            
        try:
            with open(self.ruta_codigo, "w", encoding="utf-8") as f:
                f.write(codigo_a_guardar)
            return True
        except Exception as e:
            self.status_label.configure(text=f"Error al guardar: {e}", text_color="#FF4C4C")
            return False

    def accion_editar_codigo(self):
        if not self.modo_edicion:
            self.modo_edicion = True
            self.btn_editar.configure(text="Guardar Código", fg_color="#E74C3C", hover_color="#C0392B")
            self.caja_texto.configure(state="normal")
            self.status_label.configure(text="Estado: MODO EDICIÓN (Escribe en la caja inferior)", text_color="#D4AC0D")
            
        else:
            if self._guardar_codigo_archivo():
                self.modo_edicion = False
                self.btn_editar.configure(text="Editar Código", fg_color="#D4AC0D", hover_color="#B9770E")
                self.leer_codigo_generado()
                if "sin errores" in self.status_label.cget("text"):
                    self.status_label.configure(text="Estado: Cambios manuales guardados", text_color="#2FA572")

    def accion_atajo_guardar(self, event=None):
        if self.modo_edicion:
            if self._guardar_codigo_archivo():
                self.leer_codigo_generado()
                
                self.caja_texto.configure(state="normal")
                self.caja_lineas.configure(state="normal")
                
                if "sin errores" in self.status_label.cget("text"):
                    self.status_label.configure(text="Estado: Guardado rápido (Puedes seguir editando)", text_color="#569CD6")
        
        return "break"

    def on_closing(self):
        self.vision.free()
        self.destroy()