import json
import qrcode
import qrcode.image.svg
import os

def generar_qr_svg(contenido, nombre_archivo):
    # Asegurarse de que la carpeta existe
    os.makedirs(os.path.dirname(nombre_archivo), exist_ok=True)

    # 1. Configurar la fábrica para SVG
    # Existen varias opciones: SvgPathImage (más ligero), SvgImage (estándar)
    factory = qrcode.image.svg.SvgPathImage

    # 2. Crear el código QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
        image_factory=factory
    )
    qr.add_data(contenido)
    qr.make(fit=True)

    # 3. Crear la imagen SVG
    img_svg = qr.make_image()

    # 4. Guardar el archivo
    img_svg.save(nombre_archivo)
    print(f"Éxito: QR vectorial guardado como {nombre_archivo}")

# --- Tu lógica de carga de JSON ---
try:
    with open('funcion.json', 'r') as file:
        data = json.load(file)

    basic = data[0]
    for func in basic["functions"]:
        # Cambiamos el nombre de la función y la extensión
        generar_qr_svg(func["funcBit"], f"./qrcodes/{func['funcBit']}.svg")
except FileNotFoundError:
    print("Error: No se encontró el archivo funcion.json")