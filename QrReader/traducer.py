import cv2
import json
import os
import pytesseract
from pytesseract import Output
from pyzbar.pyzbar import decode

# Configuración de archivos (Asegúrate de incluir 'demo' si lo vas a usar)
archives = ["basic", "input", "demo"]

def leer_elementos_imagen(ruta_imagen):
    img = cv2.imread(ruta_imagen)
    if img is None: 
        print("Error: No se pudo cargar la imagen.")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]

    elementos_detectados = []

    # 1. DETECCIÓN DE CÓDIGOS QR
    codigos_qr = decode(thresh)
    if not codigos_qr:
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        codigos_qr = decode(blur)

    for qr in codigos_qr:
        elementos_detectados.append({
            "tipo": "comando",
            "data": qr.data.decode('utf-8'),
            "top": qr.rect.top,
            "left": qr.rect.left
        })

    # 2. DETECCIÓN DE NÚMEROS (OCR)
    ocr_data = pytesseract.image_to_data(gray, output_type=Output.DICT, config='--psm 11')
    for i in range(len(ocr_data['text'])):
        texto = ocr_data['text'][i].strip()
        if int(ocr_data['conf'][i]) > 60 and texto:
            es_numero = texto.isdigit() or (texto.replace('.', '', 1).isdigit() and texto.count('.') < 2)
            if es_numero:
                elementos_detectados.append({
                    "tipo": "numero",
                    "data": texto,
                    "top": ocr_data['top'][i],
                    "left": ocr_data['left'][i]
                })

    # 3. ORDENAMIENTO ESPACIAL
    elementos_detectados.sort(key=lambda obj: (obj["top"] // 50, obj["left"]))

    return [elem["data"] for elem in elementos_detectados]

def buscar_en_json(comando, lista_data):
    for d in lista_data:
        for categoria in ["functions", "conditionals", "variables"]:
            for f in d.get(categoria, []):
                if f.get("funcBit") == comando or f.get("condType") == comando or f.get("varType") == comando:
                    return f
    return None

def traducir():
    program = leer_elementos_imagen('program.jpg')
    if not program:
        return

    data_consolidada = []
    for arch in archives:
        try:
            with open(f'{arch}.json', 'r', encoding='utf-8') as f:
                data_consolidada.append(json.load(f))
        except FileNotFoundError:
            print(f"Advertencia: No se encontró {arch}.json")

    with open("MicroBit_Code.py", "w", encoding="utf-8") as file:
        file.write("from microbit import *\n\n")
        
        nivel_identacion = 0
        ultimo_parametro_numerico = None

        for comando in program:
            # Caso especial: Bloque de cierre "end"
            if comando.lower() == "end":
                nivel_identacion = max(0, nivel_identacion - 1)
                continue

            # Verificación de números (OCR)
            es_numero = comando.isdigit() or (comando.replace('.', '', 1).isdigit() and comando.count('.') < 2)
            if es_numero:
                ultimo_parametro_numerico = comando
                continue 

            func_data = buscar_en_json(comando, data_consolidada)
            
            if func_data:
                tabulaciones = "\t" * nivel_identacion
                
                # Determinar el valor/parámetro
                if ultimo_parametro_numerico is not None:
                    valor = str(ultimo_parametro_numerico)
                    ultimo_parametro_numerico = None
                else:
                    valor = str(func_data.get("var", ""))
                
                # Formatear strings
                is_val_number = valor.isdigit() or (valor.replace('.', '', 1).isdigit() and valor.count('.') < 2)
                if valor and not valor.startswith("Image.") and not is_val_number:
                    valor = f"'{valor}'"
                
                # Construir la instrucción de Python PURA (sin tabulaciones ni saltos de línea)
                codigo_puro = f"{func_data.get('funcPyIni', '')}{valor}{func_data.get('funcPyFin', '')}"
                
                # Escribir en el archivo
                file.write(f"{tabulaciones}{codigo_puro}\n")

                # REVISIÓN DE DOS PUNTOS: Si el código puro termina en ':', la siguiente línea se tabula
                if codigo_puro.strip().endswith(":"):
                    nivel_identacion += 1
            else:
                print(f"Comando '{comando}' no reconocido.")

    print(f"Código generado con éxito. Nivel final de identación: {nivel_identacion}")
    os.system("python -m uflash MicroBit_Code.py")

if __name__ == "__main__":
    traducir()