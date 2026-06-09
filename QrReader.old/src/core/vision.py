import cv2
import numpy as np
import threading
import time
import os
from pyzbar.pyzbar import decode, ZBarSymbol

class VisionEngine:
    def __init__(self, cnn_dir):
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        
        self.ruta_modelo = os.path.join(cnn_dir, 'numeros_impresos.onnx')
        
        if os.path.exists(self.ruta_modelo):
            self.net = cv2.dnn.readNetFromONNX(self.ruta_modelo)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        else:
            print(f"ADVERTENCIA: No se encontró {self.ruta_modelo}. Los números no se detectarán.")
            self.net = None

        self.frame_actual = None
        self.elementos_detectados = []
        
        # --- NUEVO: MEMORIA DE TRACKING PARA QRs ---
        self.historial_qrs = [] 
        
        self.lock = threading.Lock()
        self.corriendo = True
        
        self.hilo_vision = threading.Thread(target=self._bucle_procesamiento, daemon=True)
        self.hilo_vision.start()

    def _bucle_procesamiento(self):
        while self.corriendo:
            frame_a_procesar = None
            
            with self.lock:
                if self.frame_actual is not None:
                    frame_a_procesar = self.frame_actual.copy()
            
            if frame_a_procesar is not None:
                nuevos_elementos = self.getProcessedFrame(frame_a_procesar)
                
                with self.lock:
                    self.elementos_detectados = nuevos_elementos
            
            time.sleep(0.2)

    def getProcessedFrame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray_clahe = clahe.apply(gray)
        blur = cv2.GaussianBlur(gray_clahe, (5,5), 0)
        thresh_adapt = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 5)
        _, thresh_otsu = cv2.threshold(gray_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        detecciones_brutas = decode(thresh_adapt, symbols=[ZBarSymbol.QRCODE]) + \
                             decode(thresh_otsu, symbols=[ZBarSymbol.QRCODE]) + \
                             decode(gray_clahe, symbols=[ZBarSymbol.QRCODE])

        qrs_frame_actual = []
        centros_frame = []

        for qr in detecciones_brutas:
            cx = qr.rect.left + (qr.rect.width / 2)
            cy = qr.rect.top + (qr.rect.height / 2)
            es_dup = any(abs(cx - c[0]) < 20 and abs(cy - c[1]) < 20 for c in centros_frame)
            if not es_dup:
                qrs_frame_actual.append(qr)
                centros_frame.append((cx, cy))
                
        # --- LÓGICA DE MEMORIA (ANTI-PARPADEO) ---
        for item in self.historial_qrs:
            item['ttl'] -= 1
            
        for qr, (cx, cy) in zip(qrs_frame_actual, centros_frame):
            encontrado = False
            for item in self.historial_qrs:
                if abs(item['centro'][0] - cx) < 60 and abs(item['centro'][1] - cy) < 60:
                    item['qr_obj'] = qr
                    item['centro'] = (cx, cy)
                    item['rect'] = qr.rect
                    item['data'] = qr.data.decode('utf-8')
                    item['ttl'] = 10 
                    encontrado = True
                    break
            
            if not encontrado:
                self.historial_qrs.append({
                    'qr_obj': qr,
                    'centro': (cx, cy),
                    'rect': qr.rect,
                    'data': qr.data.decode('utf-8'),
                    'ttl': 10
                })
                
        self.historial_qrs = [item for item in self.historial_qrs if item['ttl'] > 0]
        
        elementos_detectados = []

        for item in self.historial_qrs:
            elementos_detectados.append({
                "tipo": "comando",
                "data": item['data'],
                "top": item['rect'].top,
                "left": item['rect'].left,
                "qr_obj": item['qr_obj']
            })

        if not self.historial_qrs:
            return elementos_detectados
            
        ancho_medio_qr = sum(item['rect'].width for item in self.historial_qrs) / len(self.historial_qrs)

        margen_prohibido = int(ancho_medio_qr * 0.70)
        zonas_prohibidas = []
        for item in self.historial_qrs:
            rect = item['rect']
            zonas_prohibidas.append({
                'x1': rect.left - margen_prohibido,
                'y1': rect.top - margen_prohibido,
                'x2': rect.left + rect.width + margen_prohibido,
                'y2': rect.top + rect.height + margen_prohibido
            })

        blur_ocr = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Constante C en 10. Perfecta para no borrar tinta.
        thresh_ocr = cv2.adaptiveThreshold(blur_ocr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        
        thresh_inv = cv2.bitwise_not(thresh_ocr)

        # Borrado de las zonas prohibidas (QRs)
        for z in zonas_prohibidas:
            x1 = max(0, int(z['x1']))
            y1 = max(0, int(z['y1']))
            x2 = min(thresh_inv.shape[1], int(z['x2']))
            y2 = min(thresh_inv.shape[0], int(z['y2']))
            cv2.rectangle(thresh_inv, (x1, y1), (x2, y2), 0, -1) 

        contornos, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
        areas_qrs = [item['rect'].width * item['rect'].height for item in self.historial_qrs]
        
        if areas_qrs:
            area_media_qr = sum(areas_qrs) / len(areas_qrs)
            # 1. BAJAMOS AL 0.5%. Los números pueden ser diminutos en comparación con el QR.
            area_minima = area_media_qr * 0.005 
            area_maxima = area_media_qr * 0.40
        else:
            area_minima, area_maxima = 600, 9000
        
        for c in contornos:
            x, y, w, h = cv2.boundingRect(c)
            area_caja = w * h
            
            if area_minima < area_caja < area_maxima:
                
                if h > (ancho_medio_qr * 0.85):
                    continue

                aspect_ratio = float(w)/h
                
                # 2. BAJAMOS A 0.08. Un '1' dibujado a lo lejos es casi una línea vertical perfecta.
                if 0.08 < aspect_ratio < 1.1: 
                    
                    # --- EL NUEVO FILTRO DE RANGO DINÁMICO (MINMAX) ---
                    pad_c = 5
                    y1_c = max(0, y - pad_c)
                    y2_c = min(gray.shape[0], y + h + pad_c)
                    x1_c = max(0, x - pad_c)
                    x2_c = min(gray.shape[1], x + w + pad_c)
                    
                    roi_gris = gray[y1_c:y2_c, x1_c:x2_c]
                    
                    if roi_gris.size > 0:
                        # Buscamos el píxel más negro (min) y el más blanco (max) de esa cajita
                        min_val, max_val, _, _ = cv2.minMaxLoc(roi_gris)
                        rango_dinamico = max_val - min_val
                        
                        # Si no hay un contraste brutal (> 55) o si el fondo no es mínimamente claro (> 130), es sombra.
                        if rango_dinamico < 55 or max_val < 130:
                            continue
                    else:
                        continue
                    # ---------------------------------------------------

                    area_real_trazo = cv2.contourArea(c)
                    densidad = area_real_trazo / float(area_caja)
                    
                    # 3. BAJAMOS DENSIDAD. El número 1 y el 7 tienen mucha caja vacía.
                    if densidad > 0.10: 
                    
                        centro_c_x = x + w/2
                        centro_c_y = y + h/2

                        en_zona_prohibida = any(
                            z['x1'] < centro_c_x < z['x2'] and z['y1'] < centro_c_y < z['y2'] 
                            for z in zonas_prohibidas
                        )
                        if en_zona_prohibida:
                            continue

                        distancia_minima_qr = min(
                            ((centro_c_x - (item['rect'].left + item['rect'].width/2))**2 + 
                             (centro_c_y - (item['rect'].top + item['rect'].height/2))**2)**0.5
                            for item in self.historial_qrs
                        )
                        
                        if distancia_minima_qr > (ancho_medio_qr * 3.0):
                            continue
                        
                        if self.net is not None:
                            roi = thresh_inv[y:y+h, x:x+w]
                            
                            if roi.size == 0 or w == 0 or h == 0:
                                continue

                            escala = 20.0 / max(w, h)
                            nuevo_w = max(1, int(w * escala))
                            nuevo_h = max(1, int(h * escala))

                            interpolacion = cv2.INTER_CUBIC if escala > 1.0 else cv2.INTER_AREA
                            roi_redimensionado = cv2.resize(roi, (nuevo_w, nuevo_h), interpolation=interpolacion)
                            
                            lienzo = np.zeros((28, 28), dtype=np.float32)
                            
                            y_off = (28 - nuevo_h) // 2
                            x_off = (28 - nuevo_w) // 2
                            
                            lienzo[y_off:y_off+nuevo_h, x_off:x_off+nuevo_w] = roi_redimensionado / 255.0
                            
                            blob = cv2.dnn.blobFromImage(lienzo, 1.0, (28, 28), (0,0,0), swapRB=False, crop=False)
                            self.net.setInput(blob)
                            out = self.net.forward()
                            
                            logits = out[0]
                            exp_logits = np.exp(logits - np.max(logits))
                            probs = exp_logits / np.sum(exp_logits)
                            
                            clase_predicha = np.argmax(probs)
                            confianza = probs[clase_predicha] * 100
                            
                            # 4. RELAJAMOS LA IA. Le pedimos solo un 65% temporalmente para ver si estaba dudando.
                            if confianza > 65.0:
                                es_duplicado_num = any(abs(centro_c_x - elem["left"]) < 20 and abs(centro_c_y - elem["top"]) < 20 for elem in elementos_detectados if elem["tipo"] == "numero")
                                if not es_duplicado_num:
                                    elementos_detectados.append({
                                        "tipo": "numero",
                                        "data": str(clase_predicha),
                                        "top": y,
                                        "left": centro_c_x,
                                        "bbox": (x, y, w, h)
                                    })

        elementos_detectados.sort(key=lambda obj: (obj["top"] // 50, obj["left"]))
        return elementos_detectados

    def markElems(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, None, []
        
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        
        with self.lock:
            self.frame_actual = frame.copy()
            elementos = list(self.elementos_detectados)

        for elem in elementos:
            texto = elem["data"]
            
            if elem["tipo"] == "comando":
                qr = elem["qr_obj"]
                puntos = qr.polygon
                if len(puntos) == 4:
                    pts = np.array(puntos, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(frame, [pts], True, (0, 255, 255), 3)
                else:
                    rect = qr.rect
                    cv2.rectangle(frame, (rect.left, rect.top), (rect.left + rect.width, rect.top + rect.height), (0, 255, 255), 3)
                
                x_texto = qr.rect.left
                y_texto = max(0, qr.rect.top - 10) 
                cv2.putText(frame, texto, (x_texto, y_texto), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
            
            elif elem["tipo"] == "numero":
                x, y, w, h = elem["bbox"]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
                y_texto = max(0, y - 10)
                cv2.putText(frame, f"Num: {texto}", (x, y_texto), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame, frame_rgb, [elem["data"] for elem in elementos]
    
    def get_command_matrix(self):
        with self.lock:
            elementos = list(self.elementos_detectados)
            
        elementos.sort(key=lambda obj: obj["top"])
        
        filas = []
        fila_actual = []
        top_referencia = -1
        
        for elem in elementos:
            if top_referencia == -1:
                top_referencia = elem["top"]
                fila_actual.append(elem)
            elif abs(elem["top"] - top_referencia) < 50:
                fila_actual.append(elem)
            else:
                fila_actual.sort(key=lambda obj: obj["left"])
                filas.append(fila_actual)
                fila_actual = [elem]
                top_referencia = elem["top"]
                
        if fila_actual:
            fila_actual.sort(key=lambda obj: obj["left"])
            filas.append(fila_actual)
            
        matriz = []
        if filas:
            min_left = min(f[0]["left"] for f in filas)
            ancho_columna = 90 
            
            for fila in filas:
                num_indentaciones = max(0, int(round((fila[0]["left"] - min_left) / ancho_columna)))
                
                fila_strings = [""] * num_indentaciones
                for elem in fila:
                    fila_strings.append(elem["data"])
                    
                matriz.append(fila_strings)
                
        return matriz
    
    def takePhoto(self, frame, ruta_destino):
        cv2.imwrite(ruta_destino, frame)

    def getPhoto(self, ruta_origen):
        return cv2.imread(ruta_origen)
    
    def free(self):
        self.corriendo = False 
        self.cap.release()