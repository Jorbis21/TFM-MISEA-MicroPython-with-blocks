import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
from pyzbar.pyzbar import decode
import traducer
import os
import threading  # Para evitar que la cámara se congele al hablar
import pyttsx3    # Motor de texto a voz

class AppCamara(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.textos_qr_actuales = []
        self.title("Analizador de Cámara USB")
        self.geometry("1920x1080") 
        
        # --- Configuración de la Cámara ---
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        
        # --- Layout ---
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=0) 
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        # --- 1. PANEL LATERAL (Columna 0) ---
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

        # NUEVO: Botón Leer Código
        self.btn_leer = ctk.CTkButton(
            self.frame_botones, 
            text="Leer Código en Alto", 
            command=self.accion_leer_codigo,
            width=180,
            height=45,
            corner_radius=8,
            fg_color="#E67E22",     # Color Naranja
            hover_color="#D35400",  # Naranja oscuro
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
            fg_color="#8E44AD",     # Color Morado para distinguirlo
            hover_color="#732D91",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.btn_leer_qrs.pack(padx=5, pady=2, side="left", expand=True)

        self.status_label = ctk.CTkLabel(self.sidebar, text="Estado: Cámara Activa", text_color="gray")
        self.status_label.pack(side="bottom", pady=5)

        # --- 2. ÁREA DEL VISOR (Columna 1) ---
        self.contenedor_visor = ctk.CTkFrame(self)
        self.contenedor_visor.grid(row=0, column=1, rowspan = 2, padx=(5, 2), pady=5, sticky="nsew")
        
        self.video_label = ctk.CTkLabel(self.contenedor_visor, text="")
        self.video_label.pack(expand=True, fill="both", padx=0, pady=0)

        # --- 3. ÁREA DE CÓDIGO ---
        self.contenedor_codigo = ctk.CTkFrame(self)
        self.contenedor_codigo.grid(row=1, column=0, padx=(10, 20), pady=20, sticky="nsew")

        self.titulo_codigo = ctk.CTkLabel(self.contenedor_codigo, text="MicroBit_Code.py", font=ctk.CTkFont(size=16, weight="bold"))
        self.titulo_codigo.pack(padx=20, pady=(15, 5))

        self.caja_texto = ctk.CTkTextbox(self.contenedor_codigo, wrap="none", font=ctk.CTkFont(family="Consolas", size=14))
        self.caja_texto.pack(expand=True, fill="both", padx=15, pady=(0, 15))

        self.leer_codigo_generado()
        self.actualizar_frame()

    def actualizar_frame(self):
        ret, frame = self.cap.read()
        
        if ret:
            # --- LÓGICA DE ESTABILIZACIÓN AVANZADA ---
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 1. Normalización de luz (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray_clahe = clahe.apply(gray)
            
            # 2. Capa A: Umbral Adaptativo (Bueno para luces irregulares)
            blur = cv2.GaussianBlur(gray_clahe, (5, 5), 0)
            thresh_adapt = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                 cv2.THRESH_BINARY, 51, 5)
            
            # 3. Capa B: Umbral Otsu (Excelente para contrastes duros como QRs)
            _, thresh_otsu = cv2.threshold(gray_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # 4. DISPARO TRIPLE: Escaneamos las 3 versiones y sumamos todos los resultados brutos
            detecciones_brutas = decode(thresh_adapt) + decode(thresh_otsu) + decode(gray_clahe)
            
            # 5. FILTRADO DE DUPLICADOS: Como el mismo QR se detectará en varias capas, nos quedamos solo con uno
            codigos_qr = []
            centros_vistos = []
            
            for qr in detecciones_brutas:
                # Calculamos el centro geométrico de este QR
                centro_x = qr.rect.left + (qr.rect.width / 2)
                centro_y = qr.rect.top + (qr.rect.height / 2)
                
                # Comprobamos si ya tenemos un QR guardado a menos de 30 pixeles de este punto
                es_duplicado = any(abs(centro_x - cx) < 30 and abs(centro_y - cy) < 30 for cx, cy in centros_vistos)
                
                if not es_duplicado:
                    codigos_qr.append(qr)
                    centros_vistos.append((centro_x, centro_y))
            
            # TRUCO: Pyzbar a veces prefiere la escala de grises pura si el QR es muy pequeño.
            # Si con el umbral detecta muy pocos, escaneamos la imagen CLAHE directamente.
            if len(codigos_qr) < 5: 
                codigos_qr = decode(gray_clahe)

            codigos_qr.sort(key=lambda obj: obj.rect.top)
            # Guardamos los textos limpios en la variable global para que el botón pueda leerlos
            self.textos_qr_actuales = [qr.data.decode('utf-8') for qr in codigos_qr]

            # Dibujar un recuadro amarillo y el TEXTO por cada QR detectado
            for qr in codigos_qr:
                texto_qr = qr.data.decode('utf-8')
                
                # (El resto del código de dibujo se queda exactamente igual...)
                puntos = qr.polygon
                if len(puntos) == 4:
                    pts = np.array(puntos, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(frame, [pts], True, (0, 255, 255), 3)
                else:
                    rect = qr.rect
                    cv2.rectangle(frame, (rect.left, rect.top), 
                                  (rect.left + rect.width, rect.top + rect.height), 
                                  (0, 255, 255), 3)
                
                rect = qr.rect
                x_texto = rect.left
                y_texto = max(0, rect.top - 10) 
                cv2.putText(frame, texto_qr, (x_texto, y_texto), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
            # ---------------------------------------

            # Convertir de BGR a RGB... (el resto sigue igual)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(frame_rgb)
            img_tk = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(540, 960))
            self.video_label.configure(image=img_tk)
            self.video_label.image = img_tk

        self.after(15, self.actualizar_frame)

    def accion_capturar(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            cv2.imwrite("program.jpg", frame)
            self.status_label.configure(text="Estado: Procesando...", text_color="orange")
            self.update() 
            
            traducer.traducir()
            
            self.leer_codigo_generado()
            self.status_label.configure(text="Estado: ¡Completado!", text_color="green")
            self.update()

    def accion_enviar(self):
        traducer.subir()

    # --- NUEVAS FUNCIONES DE LECTURA DE VOZ ---
    def accion_leer_codigo(self):
        # Lanzamos la lectura en un hilo secundario (daemon=True hace que el hilo muera si cerramos la app)
        hilo_voz = threading.Thread(target=self._tarea_hablar, daemon=True)
        hilo_voz.start()

    def _tarea_hablar(self):
        # Inicializamos el motor DENTRO del hilo para evitar conflictos en Windows
        motor_tts = pyttsx3.init()
        
        # Ajustamos la velocidad de lectura (por defecto suele ser muy rápido, 150 es más natural)
        motor_tts.setProperty('rate', 150) 
        
        try:
            with open("MicroBit_Code.py", "r", encoding="utf-8") as file:
                codigo = file.read()
            
            # Filtramos símbolos típicos de Python para que la lectura sea más amigable
            codigo_limpio = codigo.replace("*", "todo").replace("(", " paréntesis ").replace(")", "").replace(":", " dos puntos.")
            texto_final = f"El programa actual es el siguiente... {codigo_limpio}"
            motor_tts.say(texto_final)
            motor_tts.runAndWait()
            
        except FileNotFoundError:
            motor_tts.say("Aún no se ha generado ningún código.")
            motor_tts.runAndWait()
    # ------------------------------------------

    def accion_leer_qrs_pantalla(self):
        hilo_voz_qrs = threading.Thread(target=self._tarea_hablar_qrs, daemon=True)
        hilo_voz_qrs.start()

    def _tarea_hablar_qrs(self):
        motor_tts = pyttsx3.init()
        motor_tts.setProperty('rate', 150)
        try:
            # Hacemos una copia de la lista por si la cámara actualiza el frame mientras hablamos
            qrs_a_leer = list(self.textos_qr_actuales)

            if not qrs_a_leer:
                motor_tts.say("No detecto ningún bloque en la mesa.")
                motor_tts.runAndWait()
            else:
                motor_tts.say(f"Detectados {len(qrs_a_leer)} bloques. Leyendo de arriba a abajo:")
                
                # Unimos todos los textos con puntos para que el motor haga pausas al leer
                texto_unido = ". ".join(qrs_a_leer)
                # Limpiamos guiones bajos comunes en nombres de variables para que suene mejor
                texto_limpio = texto_unido.replace("_", " ")
                
                motor_tts.say(texto_limpio)
                motor_tts.runAndWait()
        except FileNotFoundError:
            motor_tts.say("No se ha detectado ningún QR")
            motor_tts.runAndWait()
    
    def leer_codigo_generado(self):
        try:
            with open("MicroBit_Code.py", "r", encoding="utf-8") as file:
                codigo = file.read()
            
            self.caja_texto.configure(state="normal")
            self.caja_texto.delete("1.0", "end")
            self.caja_texto.insert("1.0", codigo)
            self.caja_texto.configure(state="disabled")
            
        except FileNotFoundError:
            self.caja_texto.configure(state="normal")
            self.caja_texto.delete("1.0", "end")
            self.caja_texto.insert("1.0", "# El archivo MicroBit_Code.py aún no se ha generado.\n# Toma una foto para empezar.")
            self.caja_texto.configure(state="disabled")

    def on_closing(self):
        self.cap.release()
        self.destroy()

if __name__ == "__main__":
    app = AppCamara()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()