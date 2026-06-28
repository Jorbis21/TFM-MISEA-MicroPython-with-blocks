import json
import qrcode
import os
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

# --- CÁLCULO DINÁMICO DE RUTAS SEGÚN TU ESTRUCTURA ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "data", "config")
OUTPUTS_DIR = os.path.join(BASE_DIR, "workspace", "outputs")
QRCODES_DIR = os.path.join(OUTPUTS_DIR, "qrcodes")

archives = ["functions", "variables", "conditionals"]

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
    
    return nombre_archivo

def crear_pdf_de_qrs(lista_imagenes, nombre_pdf="hoja_qrs.pdf", tamano_mm=50):
    if not lista_imagenes:
        print("No hay imágenes para añadir al PDF.")
        return

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    x_start = 10
    y_start = 10
    margen = 10
    limite_x = 200 
    limite_y = 270 
    
    x, y = x_start, y_start
    
    for img_path in lista_imagenes:
        pdf.image(img_path, x=x, y=y, w=tamano_mm)
        x += tamano_mm + margen
        
        if (x + tamano_mm) > limite_x: 
            x = x_start
            y += tamano_mm + margen + 10 
            
        if (y + tamano_mm) > limite_y:
            pdf.add_page()
            x, y = x_start, y_start
            
    ruta_pdf_final = os.path.join(OUTPUTS_DIR, nombre_pdf)
    pdf.output(ruta_pdf_final)
    print(f"\nPDF generado con éxito en: {ruta_pdf_final}")

def crear_pdf_pruebas(comando):
    ruta_qr = generar_qr_con_texto(comando, os.path.join(QRCODES_DIR, "pruebas", f"{comando}.png"))
    nombre_pdf = f"prueba_tamanos_{comando}.pdf"
    
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"Hoja de Calibracion de Camara: '{comando}'", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt="IMPORTANTE: Imprime esta hoja sin escalar (Escala 100%)", ln=True)
    pdf.ln(10)
    
    tamanos = [
        {"cm": 3.0, "mm": 30},
        {"cm": 2.5, "mm": 25},
        {"cm": 2.0, "mm": 20},
        {"cm": 1.5, "mm": 15}
    ]
    
    x_start = 20
    y_start = 60
    
    for tam in tamanos:
        pdf.set_font("Arial", 'B', 10)
        pdf.text(x_start, y_start - 5, f"{tam['cm']} cm")
        pdf.image(ruta_qr, x=x_start, y=y_start, w=tam['mm'])
        x_start += tam['mm'] + 20 
        
    ruta_pdf_final = os.path.join(OUTPUTS_DIR, nombre_pdf)
    pdf.output(ruta_pdf_final)
    print(f"\nPDF de calibración generado con éxito en: {ruta_pdf_final}")


if __name__ == "__main__":
    print("--- GENERADOR DE CÓDIGOS QR ---")
    print("1. Generar hoja completa de bloques (Lee todos los JSON)")
    print("2. Generar hoja de calibración de tamaños (Para pruebas de cámara)")
    print("3. Generar hoja de QRs personalizados (Eliges cuáles y el tamaño)")
    print("-------------------------------")
    
    opcion = input("Elige una opción (1, 2 o 3): ").strip()

    if opcion == "1":
        try:
            input_tam = input("\n¿De qué tamaño quieres los QR? (Introduce el valor en cm, ej: 3, 4.5, 5) [Por defecto: 5]: ").strip()
            if input_tam == "":
                tamano_mm = 50 
            else:
                tamano_mm = int(float(input_tam) * 10) 
        except ValueError:
            print("Valor introducido inválido. Se usará el tamaño por defecto de 5 cm.")
            tamano_mm = 50

        print(f"Generando todos los QRs a {tamano_mm / 10} cm...")

        lista_de_imagenes = []
        for arch in archives:
            ruta_json = os.path.join(CONFIG_DIR, f"{arch}.json")
            
            if os.path.exists(ruta_json):
                with open(ruta_json, 'r', encoding='utf-8') as f:
                    # Cargamos el nuevo JSON aplanado
                    subdat = json.load(f)
                    
                    # Determinamos en qué carpeta meter el PNG basándonos en el nombre del archivo
                    if arch == "functions":
                        carpeta_dest = "funciones"
                    elif arch == "conditionals":
                        carpeta_dest = "condiciones"
                    else:
                        carpeta_dest = "variables"

                    # Iteramos solo por las claves maestras (el texto del bloque)
                    for comando in subdat.keys():
                        ruta_dest = os.path.join(QRCODES_DIR, carpeta_dest, f"{comando}.png")
                        lista_de_imagenes.append(generar_qr_con_texto(comando, ruta_dest))
            else:
                print(f"Advertencia: No se encontró el archivo {ruta_json}, se omitirá.")

        crear_pdf_de_qrs(lista_de_imagenes, nombre_pdf="hoja_qrs_completa.pdf", tamano_mm=tamano_mm)

    elif opcion == "2":
        comando_prueba = input("\nEscribe el nombre del comando para la prueba (ej. 'para siempre'): ").strip()
        if not comando_prueba:
            comando_prueba = "para siempre"
            
        crear_pdf_pruebas(comando_prueba)
        
    elif opcion == "3":
        try:
            input_tam = input("\n¿De qué tamaño quieres los QR? (Introduce el valor en cm, ej: 3, 4.5, 5) [Por defecto: 5]: ").strip()
            if input_tam == "":
                tamano_mm = 50 
            else:
                tamano_mm = int(float(input_tam) * 10) 
        except ValueError:
            print("Valor introducido inválido. Se usará el tamaño por defecto de 5 cm.")
            tamano_mm = 50

        print("\nIntroduce los comandos que deseas generar separados por comas.")
        print("Ejemplo: para siempre, mostrar, corazon, numero")
        comandos_input = input("Comandos: ").strip()
        
        if not comandos_input:
            print("No se introdujeron comandos. Abortando.")
        else:
            lista_comandos = [cmd.strip() for cmd in comandos_input.split(",") if cmd.strip()]
            
            print(f"\nGenerando {len(lista_comandos)} QRs personalizados a {tamano_mm / 10} cm...")
            
            lista_de_imagenes = []
            for comando in lista_comandos:
                ruta_dest = os.path.join(QRCODES_DIR, "personalizados", f"{comando}.png")
                lista_de_imagenes.append(generar_qr_con_texto(comando, ruta_dest))
                
            crear_pdf_de_qrs(lista_de_imagenes, nombre_pdf="qrs_personalizados.pdf", tamano_mm=tamano_mm)

    else:
        print("Opción no válida. Cerrando script.")