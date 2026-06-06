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
        
        # --- CARGA DEL MODELO CNN (MNIST) ---
        self.ruta_modelo = os.path.join(cnn_dir, 'mnist.onnx')
        if os.path.exists(self.ruta_modelo):
            self.net = cv2.dnn.readNetFromONNX(self.ruta_modelo)
        else:
            print(f"ADVERTENCIA: No se encontró {self.ruta_modelo}. Los números no se detectarán.")
            self.net = None

        # --- MEMORIA COMPARTIDA ENTRE HILOS ---
        self.frame_actual = None
        self.elementos_detectados = []
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

        codigos_qr = []
        centros = []

        for qr in detecciones_brutas:
            centro_x = qr.rect.left + (qr.rect.width / 2)
            centro_y = qr.rect.top + (qr.rect.height / 2)
            es_dup = any(abs(centro_x - cx) < 30 and abs(centro_y - cy) < 30 for cx, cy in centros)
            if not es_dup:
                codigos_qr.append(qr)
                centros.append((centro_x, centro_y))
        
        elementos_detectados = []

        for qr in codigos_qr:
            elementos_detectados.append({
                "tipo": "comando",
                "data": qr.data.decode('utf-8'),
                "top": qr.rect.top,
                "left": qr.rect.left,
                "qr_obj": qr
            })

        # Preprocesamiento para números
        blur_ocr = cv2.GaussianBlur(gray, (7, 7), 0)
        thresh_ocr = cv2.adaptiveThreshold(blur_ocr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15)
        kernel = np.ones((3,3), np.uint8)
        processed_ocr = cv2.morphologyEx(thresh_ocr, cv2.MORPH_OPEN, kernel)
        
        # Para MNIST, necesitamos fondo negro y número blanco
        thresh_inv = cv2.bitwise_not(processed_ocr)
        contornos, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        zonas_prohibidas = []
        for qr in codigos_qr:
            zonas_prohibidas.append({
                'x1': qr.rect.left - 15,
                'y1': qr.rect.top - 15,
                'x2': qr.rect.left + qr.rect.width + 15,
                'y2': qr.rect.top + qr.rect.height + 15
            })
            
        # --- BARRERA 1: CÁLCULO DINÁMICO DE ÁREA RELATIVA ---
        # Calculamos cuánto mide un QR en esta imagen concreta según la altura a la que esté la cámara
        areas_qrs = [qr.rect.width * qr.rect.height for qr in codigos_qr]
        
        if areas_qrs:
            area_media_qr = sum(areas_qrs) / len(areas_qrs)
            # Un número (la tinta negra) suele ser entre un 5% y un 80% del área total del bloque QR que lo acompaña
            area_minima = area_media_qr * 0.05
            area_maxima = area_media_qr * 0.80
        else:
            # Valores de rescate estáticos por si en este frame exacto no hemos visto ningún QR
            area_minima, area_maxima = 2500, 20000
        
        for c in contornos:
            x, y, w, h = cv2.boundingRect(c)
            area_caja = w * h
            
            # Aplicamos el filtro dinámico en lugar del estático
            if area_minima < area_caja < area_maxima:
                aspect_ratio = float(w)/h
                
                # BARRERA 2: Proporción estricta (Evitamos cuadrados perfectos o líneas planas)
                if 0.15 < aspect_ratio < 0.9: 
                    
                    # BARRERA 3: Densidad (Filtra las vetas del suelo)
                    area_real_trazo = cv2.contourArea(c)
                    densidad = area_real_trazo / float(area_caja)
                    
                    if densidad > 0.15:
                    
                        centro_c_x = x + w/2
                        centro_c_y = y + h/2

                        en_zona_prohibida = any(
                            z['x1'] < centro_c_x < z['x2'] and z['y1'] < centro_c_y < z['y2'] 
                            for z in zonas_prohibidas
                        )
                        
                        if not en_zona_prohibida and self.net is not None:
                            pad = 15
                            y1 = max(0, y - pad)
                            y2 = min(processed_ocr.shape[0], y + h + pad)
                            x1 = max(0, x - pad)
                            x2 = min(processed_ocr.shape[1], x + w + pad)
                            
                            roi = thresh_inv[y1:y2, x1:x2]
                            
                            if roi.size == 0:
                                continue

                            escala = 20.0 / max(w, h)
                            roi_redimensionado = cv2.resize(roi, (0,0), fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
                            
                            lienzo = np.zeros((28, 28), dtype=np.float32)
                            h_r, w_r = roi_redimensionado.shape
                            
                            if h_r > 28 or w_r > 28:
                                roi_redimensionado = cv2.resize(roi_redimensionado, (28, 28), interpolation=cv2.INTER_AREA)
                                h_r, w_r = 28, 28

                            y_off = (28 - h_r) // 2
                            x_off = (28 - w_r) // 2
                            
                            lienzo[y_off:y_off+h_r, x_off:x_off+w_r] = roi_redimensionado / 255.0
                            
                            blob = cv2.dnn.blobFromImage(lienzo, 1.0, (28, 28), (0,0,0), swapRB=False, crop=False)
                            self.net.setInput(blob)
                            out = self.net.forward()
                            
                            logits = out[0]
                            exp_logits = np.exp(logits - np.max(logits))
                            probs = exp_logits / np.sum(exp_logits)
                            
                            clase_predicha = np.argmax(probs)
                            confianza = probs[clase_predicha] * 100
                            
                            if confianza > 65.0:
                                es_duplicado_num = any(abs(centro_c_x - elem["left"]) < 30 and abs(centro_c_y - elem["top"]) < 30 for elem in elementos_detectados if elem["tipo"] == "numero")
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
    
    def takePhoto(self, frame, ruta_destino):
        cv2.imwrite(ruta_destino, frame)

    def getPhoto(self, ruta_origen):
        return cv2.imread(ruta_origen)
    
    def free(self):
        self.corriendo = False 
        self.cap.release()