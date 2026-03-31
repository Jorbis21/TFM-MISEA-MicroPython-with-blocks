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
    
    # SOLUCIÓN: Usamos las dimensiones máximas (celda completa) 
    # en lugar de las dimensiones locales recortadas
    sector_w = max_w / 2
    sector_h = max_h / 3
    
    puntos_dentro = []
    # Usamos w_local y h_local para saber qué puntos pertenecen a esta letra
    for (px, py) in puntos_originales:
        if (x_caja <= px <= x_caja + w_local) and (y_caja <= py <= y_caja + h_local):
            puntos_dentro.append((px, py))
            
    for (px, py) in puntos_dentro:
        # Usamos sector_w y sector_h globales para ubicarlos en la cuadrícula
        columna = 0 if px < (x_caja + sector_w) else 1
        
        fila = int((py - y_caja) / sector_h)
        fila = min(fila, 2) 
        
        indice = fila + (columna * 3)
        celda_array[indice] = 1
        
    return "".join(map(str, celda_array))

def procesar_imagen_braille(ruta_imagen, braille_dict):
    # 1. Cargar la imagen
    img = cv2.imread(ruta_imagen)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Preprocesamiento para resaltar los puntos (ajusta los valores según la iluminación)
    # A veces es útil un threshold adaptativo por las sombras del papel
    thresh = cv2.adaptiveThreshold(img_gray, 255, 
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)

    # 3. Encontrar contornos (los puntos)
    contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    puntos_validos = []
    
    # 4. Filtrar contornos por tamaño para ignorar ruido
    for c in contornos:
        area = cv2.contourArea(c)
        # Ajusta estos valores de área según la resolución de tu imagen
        if 10 < area < 500: 
            # Obtener el centro del punto (x, y)
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                puntos_validos.append((cx, cy))
                
                # Dibujar un círculo rojo sobre el punto detectado para depurar
                cv2.circle(img, (cx, cy), 3, (0, 0, 255), -1)

    # Mostrar el resultado de la detección
    cv2.imshow("Puntos Detectados", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # Suponiendo que 'thresh' es tu imagen binarizada (fondo negro, puntos blancos)
    # Ajusta el tamaño del kernel (ancho, alto) según la resolución de tus fotos
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 18)) 
    # Suponiendo que 'img_gray' es tu imagen en escala de grises
    # Ajusta el valor del umbral (127 en este ejemplo) según tu foto
    _, thresh_invertido = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV)

    # Ahora 'thresh_invertido' tendrá los puntos blancos sobre fondo negro,
    # listo para pasárselo a la dilatación.
    # Dilatamos la imagen para fusionar los puntos cercanos
    imagen_dilatada = cv2.dilate(thresh_invertido, kernel, iterations=1)
    contornos_celdas, _ = cv2.findContours(imagen_dilatada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    cajas_letras = []
    max_w = 0
    max_h = 0
    
    for c in contornos_celdas:
        x, y, w, h = cv2.boundingRect(c)
        cajas_letras.append((x, y, w, h))
        
        # Encontramos la altura y anchura de una celda "completa" (ej. la letra 'l', 'p' o 'q')
        if w > max_w: max_w = w
        if h > max_h: max_h = h
    
    # ¡Importante! Ordenar las cajas de arriba a abajo y de izquierda a derecha
    # para poder leer el texto en el orden correcto.
    # (Aquí necesitarías una función para ordenar por 'y' primero y luego por 'x')
    for x in cajas_letras:
        k = analizar_celda(x, puntos_validos, max_w, max_h);
        print(k)
        print(braille_dict[k])

    return puntos_validos

# Uso:
puntos = procesar_imagen_braille("pa.jpg", braille_dict)
print(f"Se detectaron {len(puntos)} puntos.")