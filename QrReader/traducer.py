import cv2
import json
import os
import sys
import pytesseract
from pytesseract import Output
from pyzbar.pyzbar import decode

archives = ["basic", "input", "demo"]

def leer_elementos_imagen(ruta_imagen):
    img = cv2.imread(ruta_imagen)
    if img is None: 
        print("Error: No se pudo cargar la imagen.")
        return []
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
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
    elementos_detectados = []

    if not codigos_qr or len(codigos_qr) < 5:
        codigos_qr = decode(gray_clahe)

    for qr in codigos_qr:
        elementos_detectados.append({
            "tipo": "comando",
            "data": qr.data.decode('utf-8'),
            "top": qr.rect.top,
            "left": qr.rect.left
        })

    # OCR para números
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

    elementos_detectados.sort(key=lambda obj: (obj["top"] // 50, obj["left"]))
    return [elem["data"] for elem in elementos_detectados]

def buscar_en_json(comando, lista_data):
    for d in lista_data:
        for categoria in ["functions", "conditionals", "variables"]:
            for f in d.get(categoria, []):
                if f.get("funcBit") == comando:
                    return (f, "funcion")
                if f.get("condType") == comando:
                    return (f, "condicion")
                if f.get("varType") == comando:
                    return (f, "variable")
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
        comando_abierto = False
        str_cierre = ""
        linea_actual = "" # Búfer para guardar la línea que estamos escribiendo

        # --- NUEVA LÓGICA DE ESCRITURA E INDENTACIÓN ---
        def escribir(texto):
            nonlocal nivel_identacion, linea_actual
            file.write(texto)
            linea_actual += texto
            
            # Si introducimos un salto de línea, comprobamos la línea que acabamos de terminar
            if "\n" in linea_actual:
                partes = linea_actual.split("\n")
                # Analizamos todas las líneas completas por si escribimos varias de golpe
                for i in range(len(partes) - 1):
                    if partes[i].strip().endswith(":"):
                        nivel_identacion += 1
                # Mantenemos en el búfer lo que quede tras el último salto de línea
                linea_actual = partes[-1]

        for comando in program:
            # 1. Caso especial: Bloque "end"
            if comando.lower() == "end":
                if comando_abierto:
                    escribir(str_cierre)
                    comando_abierto = False
                    
                nivel_identacion = max(0, nivel_identacion - 1)
                continue
            
            # 2. Revisión de inicio
            if comando.lower() == "on start" and nivel_identacion > 0:
                print("Advertencia: 'on start' no puesto al principio")
                return
                
            # 3. Verificación de números detectados por OCR
            es_numero = comando.isdigit() or (comando.replace('.', '', 1).isdigit() and comando.count('.') < 2)
            if es_numero:
                escribir(f"{comando}")
                continue 

            # 4. Búsqueda en los JSON (QRs de funciones, variables y condicionales)
            func_data = buscar_en_json(comando, data_consolidada)
            
            if func_data:
                data_json = func_data[0]
                tipo_comando = func_data[1]

                if tipo_comando == "funcion":
                    # Si veníamos de una función o if anterior, lo cerramos antes de abrir la nueva
                    if comando_abierto:
                        escribir(str_cierre)
                        comando_abierto = False
                            
                    tabulaciones = "\t" * nivel_identacion
                    codigo_ini = data_json.get('funcPyIni', '')
                    escribir(f"{tabulaciones}{codigo_ini}")
                    
                    # Preparamos el cierre para cuando lleguen las variables, la siguiente función o el end
                    str_cierre = data_json.get('funcPyFin', '') + "\n"
                    comando_abierto = True
                    
                elif tipo_comando == "condicion":
                    condicion = data_json.get('cond', '')
                    escribir(f" {condicion} ")
                    
                elif tipo_comando == "variable":
                    valor = data_json.get('var', '')
                    is_val_number = valor.isdigit() or (valor.replace('.', '', 1).isdigit() and valor.count('.') < 2)
                    if valor and not valor.startswith("Image.") and not is_val_number:
                        valor = f"'{valor}'"
                    escribir(f"{valor}")
            else:
                print(f"Comando '{comando}' no reconocido.")

        # --- CIERRE DE SEGURIDAD ---
        if comando_abierto:
            escribir(str_cierre)

    print(f"Código generado con éxito. Nivel final de identación: {nivel_identacion}")
    

def subir():
    comando = f'"{sys.executable}" -m uflash MicroBit_Code.py'
    os.system(comando)

if __name__ == "__main__":
    traducir()