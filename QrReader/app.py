import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import traducer

class AppCamara(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Analizador de Cámara USB")
        self.geometry("1000x600")
        
        # --- Configuración de la Cámara ---
        # 0 es la cámara por defecto
        self.cap = cv2.VideoCapture(0)
        
        # --- Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- PANEL LATERAL ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="CONTROLES", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(padx=20, pady=(20, 10))

        self.btn_capturar = ctk.CTkButton(self.sidebar, text="Tomar Foto", command=self.accion_capturar)
        self.btn_capturar.pack(padx=20, pady=10)
        
        self.status_label = ctk.CTkLabel(self.sidebar, text="Estado: Cámara Activa", text_color="gray")
        self.status_label.pack(side="bottom", pady=20)

        # --- ÁREA DEL VISOR ---
        self.contenedor_visor = ctk.CTkFrame(self)
        self.contenedor_visor.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        # Etiqueta donde se mostrará el video
        self.video_label = ctk.CTkLabel(self.contenedor_visor, text="")
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Iniciar la actualización del video
        self.actualizar_frame()

    def actualizar_frame(self):
        # 1. Capturar frame de OpenCV
        ret, frame = self.cap.read()
        
        if ret:
            # 2. Convertir de BGR (OpenCV) a RGB (Pillow)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 3. Convertir a imagen PIL y luego a CTkImage
            img_pil = Image.fromarray(frame_rgb)
            
            # Redimensionar la imagen para que encaje en el visor (ajusta según necesites)
            img_tk = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(640, 480))
            
            # 4. Colocar la imagen en la etiqueta
            self.video_label.configure(image=img_tk)
            self.video_label.image = img_tk # Mantener referencia para evitar que el garbage collector la borre

        # 5. Llamar a esta función otra vez después de 15ms (aprox 60 FPS)
        self.after(15, self.actualizar_frame)

    def accion_capturar(self):
        ret, frame = self.cap.read()
        if ret:
            cv2.imwrite("program.jpg", frame)
            self.status_label.configure(text="Estado: ¡Foto guardada!", text_color="yellow")
            traducer.traducir()



    # Liberar la cámara al cerrar la ventana
    def on_closing(self):
        self.cap.release()
        self.destroy()

if __name__ == "__main__":
    app = AppCamara()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()