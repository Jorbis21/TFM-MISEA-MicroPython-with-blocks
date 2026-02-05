import cv2
import json
import os
from pyzbar.pyzbar import decode

def leer_multiples_qr(ruta_imagen):
    img = cv2.imread(ruta_imagen)
    if img is None: return
    
    # 1. Convertir a escala de grises
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. Aumentar el contraste y binarizar (Umbralización adaptativa)
    # Esto intentará separar el gris del azul de forma más agresiva
    thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]

    # Intentar leer en la imagen original y en la procesada
    codigos_encontrados = decode(thresh)
    
    if not codigos_encontrados:
        # Si falla, intentamos con un desenfoque ligero para eliminar ruido
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        codigos_encontrados = decode(blur)
    
    funciones = [i for i in range(len(codigos_encontrados))]

    print(f"Se detectaron {len(codigos_encontrados)} códigos.")
    i = len(codigos_encontrados) - 1
    for codigo in codigos_encontrados:
        funciones[i] = codigo.data.decode('utf-8')
        i=i-1
    return funciones


program = leer_multiples_qr('program.png')

with open('funcion.json', 'r') as file:
    data = json.load(file)

with open("MicroBit_Code.py", "w", encoding="utf-8") as file:
    file.write("from microbit import *\n\n")
    for i, func in enumerate(program):
        funcBit = next((x for x in data[0]["functions"] if x["funcBit"] == func),None)
        if(funcBit["header"] == True):
            file.write(funcBit["funcPyIni"] + "\n")
        else:
            file.write("\t" + funcBit["funcPyIni"])
            file.write(f"{funcBit["var"]}")
            file.write(funcBit["funcPyFin"] + "\n")

print("Enviando código a Micro:bit...")
os.system("python -m uflash MicroBit_Code.py")
