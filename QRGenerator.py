import json
import qrcode
from PIL import Image, ImageDraw, ImageFont

def generar_qr_con_texto(contenido, nombre_archivo):
    # 1. Crear el código QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(contenido)
    qr.make(fit=True)

    # Crear la imagen base del QR (Blanco y Negro)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    ancho, alto = img_qr.size

    # 2. Configurar el texto y la fuente
    # Intentamos cargar una fuente del sistema, si no, usamos la por defecto
    try:
        # En Windows: 'arial.ttf', en Linux: 'DejaVuSans.ttf'
        fuente = ImageFont.truetype("arial.ttf", 20)
    except:
        fuente = ImageFont.load_default()

    # Calcular espacio necesario para el texto
    draw = ImageDraw.Draw(img_qr)
    # Obtenemos las dimensiones del texto (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), contenido, font=fuente)
    ancho_texto = bbox[2] - bbox[0]
    alto_texto = bbox[3] - bbox[1]

    # 3. Crear un nuevo lienzo más alto para que quepa el texto
    nuevo_alto = alto + alto_texto + 20 # 20px de margen extra
    imagen_final = Image.new('RGB', (ancho, nuevo_alto), "white")
    
    # Pegar el QR original arriba
    imagen_final.paste(img_qr, (0, 0))

    # 4. Dibujar el texto centrado
    draw_final = ImageDraw.Draw(imagen_final)
    pos_x = (ancho - ancho_texto) // 2
    pos_y = alto  # Justo debajo del QR
    
    draw_final.text((pos_x, pos_y), contenido, fill="black", font=fuente)

    # Guardar
    imagen_final.save(nombre_archivo)
    print(f"Éxito: QR guardado como {nombre_archivo}")

with open('funcion.json', 'r') as file:
    data = json.load(file)

basic = data[0]
for func in basic["functions"]:
 generar_qr_con_texto(func["funcBit"], "./qrcodes/" + func["funcBit"]+".png")

