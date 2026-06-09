import os
import customtkinter as ctk
from PIL import Image
from core.vision import VisionEngine
from core.audio import GestorVoz
from core.translator import MicrobitTranslator

class AppCamara(ctk.CTk):
    def __init__(self, workspace_dir, config_dir, cnn_dir):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.ruta_img = os.path.join(self.workspace_dir, "inputs", "program.jpg")
        self.ruta_codigo = os.path.join(self.workspace_dir, "outputs", "MicroBit_Code.py")
        
        self.textos_qr_actuales = []
        self.title("Analizador de Cámara USB")
        self.geometry("1920x1080") 
        
        self.vision = VisionEngine(cnn_dir)

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

        # Botón Tomar Foto
        self.btn_capturar = ctk.CTkButton(
            self.frame_botones, 
            text="Tomar Foto", 
            command=self.accion_capturar,
            width=180,
            height=45,
            corner_radius=8,
            fg_color="#0052cc",
            hover_color="#003d99",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.btn_capturar.pack(padx=5, pady=2, side = "left", expand = True)
        
        # Botón Enviar a MicroBit
        self.btn_enviar = ctk.CTkButton(
            self.frame_botones, 
            text="Enviar a MicroBit", 
            command=self.accion_enviar,
            width=180,
            height=45,
            corner_radius=8,
            fg_color="#2FA572",
            hover_color="#106A43",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.btn_enviar.pack(padx=5, pady=2, side = "left", expand = True)

        # Botón Leer Código
        self.btn_leer = ctk.CTkButton(
            self.frame_botones, 
            text="Leer Código en Alto", 
            command=self.accion_leer_codigo,
            width=180,
            height=45,
            corner_radius=8,
            fg_color="#E67E22",
            hover_color="#D35400",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.btn_leer.pack(padx=5, pady=2, side = "left", expand = True)

        self.btn_leer_qrs = ctk.CTkButton(
            self.frame_botones, 
            text="Leer QRs en Pantalla", 
            command=self.accion_leer_qrs_pantalla,
            width=180,
            height=45,
            corner_radius=8,
            fg_color="#8E44AD",
            hover_color="#732D91",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.btn_leer_qrs.pack(padx=5, pady=2, side="left", expand=True)

        self.status_label = ctk.CTkLabel(self.sidebar, text="Estado: Cámara Activa", text_color="gray")
        self.status_label.pack(side="bottom", pady=5)
        
        # Área de Visor
        self.contenedor_visor = ctk.CTkFrame(self)
        self.contenedor_visor.grid(row=0, column=1, rowspan=2, padx=(5, 2), pady=5, sticky="nsew")
        self.video_label = ctk.CTkLabel(self.contenedor_visor, text="")
        self.video_label.pack(expand=True, fill="both")

        # Área de Código
        self.contenedor_codigo = ctk.CTkFrame(self)
        self.contenedor_codigo.grid(row=1, column=0, padx=(10, 20), pady=20, sticky="nsew")
        self.caja_texto = ctk.CTkTextbox(self.contenedor_codigo, wrap="none", font=ctk.CTkFont(family="Consolas", size=14))
        self.caja_texto.pack(expand=True, fill="both", padx=15, pady=(0, 15))

        self.leer_codigo_generado()
        self.actualizar_frame()
        self.traductor = MicrobitTranslator(config_dir=config_dir)

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
            
            # NUEVO: Extraemos la matriz 2D espacial en lugar de la lista plana
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

    def leer_codigo_generado(self):
        self.caja_texto.configure(state="normal")
        self.caja_texto.delete("1.0", "end")
        try:
            with open(self.ruta_codigo, "r", encoding="utf-8") as file:
                self.caja_texto.insert("1.0", file.read())
        except FileNotFoundError:
            self.caja_texto.insert("1.0", "# Archivo no generado.")
        self.caja_texto.configure(state="disabled")

    def on_closing(self):
        self.vision.free()
        self.destroy()