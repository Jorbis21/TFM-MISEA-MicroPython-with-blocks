import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import random
import torchvision.transforms as T
import onnx
from onnxsim import simplify

class CNN_Impresos(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        self.fc1 = nn.Linear(32 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.pool(torch.relu(self.conv1(x)))
        x = self.pool(torch.relu(self.conv2(x)))
        x = torch.flatten(x, 1) 
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        return x

# --- EL SECRETO: DATA AUGMENTATION EXTREMO ---
# Simulamos: Rotaciones de cámara, perspectiva (shear), alejamientos (scale) y desenfoque de lente
transformaciones = T.Compose([
    T.RandomAffine(degrees=25, translate=(0.15, 0.15), scale=(0.7, 1.15), shear=15),
    T.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5))
])

def generar_batch_datos(batch_size):
    # Forzamos Arial que es la que usas en Google Docs
    fuentes = ["arial.ttf"] 
    
    imagenes = torch.zeros(batch_size, 1, 28, 28)
    etiquetas = torch.zeros(batch_size, dtype=torch.long)
    
    for i in range(batch_size):
        numero = random.randint(0, 9)
        etiquetas[i] = numero
        
        img = Image.new('L', (28, 28), color=0)
        draw = ImageDraw.Draw(img)
        
        try:
            fuente_elegida = random.choice(fuentes)
            tamano_fuente = random.randint(18, 26) 
            font = ImageFont.truetype(fuente_elegida, tamano_fuente)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), str(numero), font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        offset_x = (28 - w) / 2
        offset_y = (28 - h) / 2
        
        draw.text((offset_x, offset_y), str(numero), fill=255, font=font)
        
        # Convertimos a tensor temporal
        array_img = np.array(img, dtype=np.float32) / 255.0
        tensor_img = torch.tensor(array_img).unsqueeze(0) # Formato [1, 28, 28]
        
        # 1. Aplicar transformaciones geométricas y blur
        tensor_img = transformaciones(tensor_img)
        
        # 2. Inyectar ruido de sensor CMOS (grano de cámara)
        ruido = torch.randn_like(tensor_img) * 0.08
        tensor_img = torch.clamp(tensor_img + ruido, 0.0, 1.0)
        
        imagenes[i, 0, :, :] = tensor_img.squeeze(0)
        
    return imagenes, etiquetas

def entrenar_modelo():
    print("Iniciando entrenamiento con Data Augmentation (simulación de cámara real)...")
    modelo = CNN_Impresos()
    optimizer = optim.Adam(modelo.parameters(), lr=0.001)
    criterio = nn.CrossEntropyLoss()
    
    # Subimos a 1500 iteraciones porque aprender de datos ruidosos es más difícil
    for epoch in range(1500): 
        datos, etiquetas = generar_batch_datos(64) 
        
        optimizer.zero_grad()
        salidas = modelo(datos)
        loss = criterio(salidas, etiquetas)
        loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Iteración {epoch}/1500 - Pérdida (Loss): {loss.item():.4f}")
            
    print("Entrenamiento completado. Generando ONNX...")
    return modelo

if __name__ == "__main__":
    modelo_entrenado = entrenar_modelo()
    modelo_entrenado.eval()

    ruta_exportacion = "numeros_impresos.onnx"
    dummy_input = torch.randn(1, 1, 28, 28)

    torch.onnx.export(
        modelo_entrenado,
        dummy_input,
        ruta_exportacion,
        input_names=['input'],
        output_names=['output'],
        opset_version=14,  
        do_constant_folding=True
    )

    try:
        model_onnx = onnx.load(ruta_exportacion)
        model_simp, check = simplify(model_onnx)
        if check:
            onnx.save(model_simp, ruta_exportacion)
            print(f"¡Modelo de combate generado y simplificado en '{ruta_exportacion}'!")
    except Exception as e:
        print(f"Error en onnxsim: {e}")