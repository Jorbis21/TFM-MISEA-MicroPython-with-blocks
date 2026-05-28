import cv2
import numpy as np

braille_dict = {
    '000000': '',
    '100000': 'a',
    '110000': 'b',
    '100100': 'c',
    '100110': 'd',
    '100010': 'e',
    '110100': 'f',
    '110110': 'g',
    '110010': 'h',
    '010100': 'i',
    '010110': 'j',
    '101000': 'k',
    '111000': 'l',
    '101100': 'm',
    '101110': 'n',
    '110111': 'ñ',
    '101010': 'o',
    '111100': 'p',
    '111110': 'q',
    '111010': 'r',
    '011100': 's',
    '011110': 't',
    '101001': 'u',
    '111001': 'v',
    '010111': 'w',
    '101101': 'x',
    '101111': 'y',
    '101011': 'z'
}

def analizar_celda(caja, puntos_originales, max_w, max_h):
    x_caja, y_caja, w_local, h_local = caja
    
    celda_array = [0, 0, 0, 0, 0, 0]
    
    sector_w = max_w / 2
    sector_h = max_h / 3
    
    puntos_dentro = []
    for (px, py) in puntos_originales:
        if (x_caja <= px <= x_caja + w_local) and (y_caja <= py <= y_caja + h_local):
            puntos_dentro.append((px, py))
            
    for (px, py) in puntos_dentro:
        columna = 0 if px < (x_caja + sector_w) else 1
        fila = int((py - y_caja) / sector_h)
        fila = min(fila, 2) 
        
        indice = fila + (columna * 3)
        celda_array[indice] = 1
        
    return "".join(map(str, celda_array))

def procesar_imagen_braille(ruta_imagen, braille_dict):
    # 1. Cargar la imagen
    img = cv2.imread(ruta_imagen)
    if img is None:
        print("Error: No se encontró la imagen.")
        return []
    
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- NUEVO: 2. Aislar el recuadro negro (ROI) ---
    # Usamos Otsu para encontrar las zonas muy oscuras (el borde del recuadro)
    _, thresh_box = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Encontrar los contornos de las cosas oscuras
    contornos_box, _ = cv2.findContours(thresh_box, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Suponemos que el recuadro dibujado es el contorno más grande en la imagen
    if contornos_box:
        caja_mayor = max(contornos_box, key=cv2.contourArea)
        x_roi, y_roi, w_roi, h_roi = cv2.boundingRect(caja_mayor)
        
        # Reducimos el área de interés unos píxeles para dejar fuera la propia línea negra
        # y que no se confunda con puntos braille
        margen = 8
        x_roi += margen
        y_roi += margen
        w_roi -= margen * 2
        h_roi -= margen * 2
        
        # Creamos una máscara blanca (todo a 255)
        mascara = np.full(img_gray.shape, 255, dtype=np.uint8)
        # Pintamos de negro (0) solo la zona interior útil del recuadro
        cv2.rectangle(mascara, (x_roi, y_roi), (x_roi + w_roi, y_roi + h_roi), 0, -1)
        
        # Combinamos: Lo que está fuera del recuadro se vuelve blanco puro (borrando todo el ruido).
        # Lo que está dentro (los puntos) mantiene su color original.
        img_gray_limpia = cv2.bitwise_or(img_gray, mascara)
    else:
        img_gray_limpia = img_gray.copy() # Si no encuentra recuadro, usa la original

    # 3. Preprocesamiento en la imagen limpia
    thresh = cv2.adaptiveThreshold(img_gray_limpia, 255, 
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 20)

    # 4. Encontrar contornos (los puntos)
    contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    puntos_validos = []
    
    # 5. Filtrar contornos por tamaño
    for c in contornos:
        area = cv2.contourArea(c)
        if 10 < area < 500: 
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                puntos_validos.append((cx, cy))
                cv2.circle(img, (cx, cy), 3, (0, 0, 255), -1)

    cv2.imshow("Filtro ROI (Fuera del recuadro es blanco)", img_gray_limpia)
    cv2.imshow("Puntos Detectados", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # 6. Agrupar puntos en Celdas (Letras)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 18)) 
    imagen_dilatada = cv2.dilate(thresh, kernel, iterations=1)
    contornos_celdas, _ = cv2.findContours(imagen_dilatada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    cajas_letras = []
    max_w = 0
    max_h = 0
    
    for c in contornos_celdas:
        x, y, w, h = cv2.boundingRect(c)
        cajas_letras.append((x, y, w, h))
        if w > max_w: max_w = w
        if h > max_h: max_h = h
    
    # --- NUEVO: 7. Ordenar de Arriba-Abajo y de Izquierda-Derecha ---
    # Si la diferencia vertical ('y') entre dos cajas es menor a la mitad de su altura, 
    # se consideran de la misma línea (fila). Luego se ordenan por 'x'.
    margen_fila = max_h // 2 if max_h > 0 else 1
    cajas_letras.sort(key=lambda b: (b[1] // margen_fila, b[0]))

    # 8. Analizar y traducir
    texto_traducido = ""
    for x in cajas_letras:
        k = analizar_celda(x, puntos_validos, max_w, max_h)
        letra = braille_dict.get(k, "?")
        texto_traducido += letra
        print(f"Patrón: {k} -> Letra: {letra}")

    print(f"\nTexto final traducido: {texto_traducido}")
    return puntos_validos

# Uso:
puntos = procesar_imagen_braille("BrailleReader/5.jpeg", braille_dict)
print(f"Se detectaron {len(puntos)} puntos.")