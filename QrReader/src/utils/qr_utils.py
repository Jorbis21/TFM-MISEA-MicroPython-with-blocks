import json
import qrcode
import os
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

archives = ["basic", "input", "demo"]
lista_de_imagenes = [] # Para guardar las rutas de los QRs generados

def generar_qr_con_texto(contenido, nombre_archivo):
    os.makedirs(os.path.dirname(nombre_archivo), exist_ok=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(contenido)
    qr.make(fit=True)

    img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = img_qr.size

    espacio_texto = 40 
    img_final = Image.new('RGB', (qr_width, qr_height + espacio_texto), 'white')
    img_final.paste(img_qr, (0, 0))

    draw = ImageDraw.Draw(img_final)
    
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), contenido, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    pos_x = (qr_width - text_width) / 2
    pos_y = qr_height + (espacio_texto - text_height) / 2 - 5 

    draw.text((pos_x, pos_y), contenido, fill="black", font=font)
    img_final.save(nombre_archivo)
    
    # IMPORTANTE: Devolvemos la ruta para el PDF
    return nombre_archivo

def crear_pdf_de_qrs(lista_imagenes, nombre_pdf="hoja_qrs.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Configuración de la cuadrícula
    x_start = 10
    y_start = 10
    ancho_qr = 50  # Tamaño en el PDF (mm)
    margen = 10
    
    x, y = x_start, y_start
    
    for img_path in lista_imagenes:
        # Añadir imagen al PDF
        pdf.image(img_path, x=x, y=y, w=ancho_qr)
        
        # Mover a la derecha
        x += ancho_qr + margen
        
        # Si llegamos al final de la fila (3 QRs por fila aprox)
        if x > 160: 
            x = x_start
            y += ancho_qr + margen + 10 # 10 extra por el espacio del texto inferior
            
        # Si llegamos al final de la página
        if y > 250:
            pdf.add_page()
            x, y = x_start, y_start
            
    pdf.output(nombre_pdf)
    print(f"\nPDF generado con éxito: {nombre_pdf}")

# --- PROCESO PRINCIPAL ---
try:
    data = []
    for arch in archives:
        with open(arch + '.json', 'r') as f:
            data.append(json.load(f))

    for subdat in data:
        # Procesar Funciones
        for func in subdat.get("functions", []):
            contenido = func["funcBit"]
            ruta = generar_qr_con_texto(contenido, f"./qrcodes/funciones/{contenido}.png")
            lista_de_imagenes.append(ruta)

        # Procesar Condicionales
        for cond in subdat.get("conditionals", []):
            contenido = cond["condType"]
            ruta = generar_qr_con_texto(contenido, f"./qrcodes/condiciones/{contenido}.png")
            lista_de_imagenes.append(ruta)

        # Procesar Variables
        for var in subdat.get("variables", []):
            contenido = var["varType"]
            ruta = generar_qr_con_texto(contenido, f"./qrcodes/variables/{contenido}.png")
            lista_de_imagenes.append(ruta)

    # Si se generaron imágenes, crear el PDF
    if lista_de_imagenes:
        crear_pdf_de_qrs(lista_de_imagenes)
    else:
        print("No se generaron QRs para añadir al PDF.")

except FileNotFoundError:
    print("Error: No se encontró uno de los archivos .json")