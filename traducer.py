import cv2
import json
import os
from pyzbar.pyzbar import decode

def leer_multiples_qr(ruta_imagen):
    img = cv2.imread(ruta_imagen)
    codigos_encontrados = decode(img)

    funciones = [i for i in range(len(codigos_encontrados))]

    if not codigos_encontrados:
        print("No se encontraron códigos QR.")
        return

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
