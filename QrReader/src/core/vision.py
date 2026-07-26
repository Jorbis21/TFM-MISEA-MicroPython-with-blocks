import cv2
import numpy as np
import threading
import time
from pyzbar.pyzbar import decode, ZBarSymbol

class VisionEngine:
    def __init__(self):
        self.camera_index = 0  
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        
        self.frame_actual = None
        self.elementos_detectados = []
        
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
            
            time.sleep(0.1) 

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
            texto = item['data']
            
            try:
                float(texto)
                tipo = "numero"
            except ValueError:
                tipo = "comando"

            elementos_detectados.append({
                "tipo": tipo,
                "data": texto,
                "top": item['rect'].top,
                "left": item['rect'].left,
                "qr_obj": item['qr_obj']
            })

        elementos_detectados.sort(key=lambda obj: (obj["top"] // 50, obj["left"]))
        return elementos_detectados

    def markElems(self, rotar_camara):
        ret, frame = self.cap.read()
        if not ret:
            return None, None, []
        
        if rotar_camara:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        
        with self.lock:
            self.frame_actual = frame.copy()
            elementos = list(self.elementos_detectados)

        for elem in elementos:
            texto = elem["data"]
            qr = elem["qr_obj"]
            puntos = qr.polygon
            
            color = (0, 255, 0) if elem["tipo"] == "numero" else (0, 255, 255)
            prefijo = "Num: " if elem["tipo"] == "numero" else ""

            if len(puntos) == 4:
                pts = np.array(puntos, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], True, color, 3)
            else:
                rect = qr.rect
                cv2.rectangle(frame, (rect.left, rect.top), (rect.left + rect.width, rect.top + rect.height), color, 3)
            
            x_texto = qr.rect.left
            y_texto = max(0, qr.rect.top - 10) 
            cv2.putText(frame, f"{prefijo}{texto}", (x_texto, y_texto), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)
        
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
        
    # =========================================================
    # NUEVO: SISTEMA DE DESBORDAMIENTO (CÓDIGO INFINITO)
    # =========================================================
    def comprobar_desbordamiento(self):
        """Escanea si hay bloques cerca de los bordes derecho e inferior."""
        with self.lock:
            if self.frame_actual is None: return None
            alto_frame, ancho_frame, _ = self.frame_actual.shape
            elementos = list(self.elementos_detectados)
            
        if not elementos: return None
        
        # Margen (en píxeles) para considerar que toca el borde
        margen_derecho = ancho_frame - 150
        margen_inferior = alto_frame - 150
        
        # Agrupamos por filas igual que en la generación de matriz
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

        nexos_derecha = []
        nexo_abajo = None
        
        # 1. Comprobar borde derecho (puede haber múltiples líneas tocando el borde)
        for fila in filas:
            ultimo_bloque = fila[-1]
            if ultimo_bloque["left"] + ultimo_bloque["qr_obj"].rect.width > margen_derecho:
                nexos_derecha.append(ultimo_bloque["data"])
                
        # 2. Comprobar borde inferior (Solo el más a la izquierda de la última fila)
        if filas:
            ultima_fila = filas[-1]
            primer_bloque = ultima_fila[0] 
            if primer_bloque["top"] + primer_bloque["qr_obj"].rect.height > margen_inferior:
                nexo_abajo = primer_bloque["data"]

        # Devolver solo si hay desbordamiento real
        if nexos_derecha or nexo_abajo:
            return {
                "derecha": nexos_derecha,
                "abajo": nexo_abajo
            }
            
        return None

    def liberar_camara(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

    def iniciar_camara(self, camera_index=None):
        if camera_index is not None:
            self.camera_index = camera_index
            
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    def takePhoto(self, frame, ruta_destino):
        cv2.imwrite(ruta_destino, frame)

    def getPhoto(self, ruta_origen):
        return cv2.imread(ruta_origen)
    
    def free(self):
        self.corriendo = False 
        self.cap.release()