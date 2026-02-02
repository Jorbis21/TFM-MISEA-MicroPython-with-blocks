import json
import qrcode

with open('funcion.json', 'r') as file:
    data = json.load(file)

basic = data[0]
for func in basic["functions"]:
 print({func["funcBit"]})
 img = qrcode.make(func["funcBit"])
 img.save("./qrcodes/" + func["funcBit"] + ".png")