import cv2
import numpy as np
import os
from pyzbar.pyzbar import decode, ZBarSymbol
from utils.strings import t

class VisionEngine:
    """Gestiona la cámara y decodifica los QRs visibles en cada frame, manteniendo un histórico corto para estabilizar la lectura y detectar cuándo el programa se sale del encuadre"""
    """Manages the camera and decodes the QRs visible in each frame, keeping a short history to stabilize the reading and detect when the program runs off the frame"""

    def __init__(self):
        """Deja el motor listo sin cámara abierta todavía ni ningún elemento detectado"""
        """Leaves the engine ready with no camera open yet and nothing detected"""
        self.camera_index = 0  
        self.cap = None
        
        self.actual_frame = None
        self.detected_elems = []
        self.qrs_history = [] 

    def update_process(self):
        """Método que procesa los QRs del frame actual"""
        """Method that process the QRs of the actual frame"""
        if self.actual_frame is not None:
            self.detected_elems = self.get_processed_frame(self.actual_frame)

    def get_processed_frame(self, frame):
        """Devuelve el frame procesado"""
        """Returns the processed frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray_clahe = clahe.apply(gray)
        blur = cv2.GaussianBlur(gray_clahe, (5,5), 0)
        thresh_adapt = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 5)
        _, thresh_otsu = cv2.threshold(gray_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        raw_detections = decode(thresh_adapt, symbols=[ZBarSymbol.QRCODE]) + \
                             decode(thresh_otsu, symbols=[ZBarSymbol.QRCODE]) + \
                             decode(gray_clahe, symbols=[ZBarSymbol.QRCODE])

        qrs_actual_frame = []
        frame_centers = []

        for qr in raw_detections:
            cx = qr.rect.left + (qr.rect.width / 2)
            cy = qr.rect.top + (qr.rect.height / 2)
            is_dup = any(abs(cx - c[0]) < 20 and abs(cy - c[1]) < 20 for c in frame_centers)
            if not is_dup:
                qrs_actual_frame.append(qr)
                frame_centers.append((cx, cy))
                
        for item in self.qrs_history:
            item['ttl'] -= 1
            
        for qr, (cx, cy) in zip(qrs_actual_frame, frame_centers):
            found = False
            for item in self.qrs_history:
                if abs(item['center'][0] - cx) < 60 and abs(item['center'][1] - cy) < 60:
                    item['qr_obj'] = qr
                    item['center'] = (cx, cy)
                    item['rect'] = qr.rect
                    item['data'] = qr.data.decode('utf-8')
                    item['ttl'] = 10 
                    found = True
                    break
            
            if not found:
                self.qrs_history.append({
                    'qr_obj': qr,
                    'center': (cx, cy),
                    'rect': qr.rect,
                    'data': qr.data.decode('utf-8'),
                    'ttl': 10
                })
                
        self.qrs_history = [item for item in self.qrs_history if item['ttl'] > 0]
        
        detected_elems = []
        for item in self.qrs_history:
            text = item['data']
            try:
                float(text)
                elem_type = "number"
            except ValueError:
                elem_type = "command"

            detected_elems.append({
                "type": elem_type,
                "data": text,
                "top": item['rect'].top,
                "left": item['rect'].left,
                "qr_obj": item['qr_obj']
            })

        detected_elems.sort(key=lambda obj: (obj["top"] // 50, obj["left"]))
        return detected_elems

    def get_marked_frame(self, rotate):
        """Lee la cámara, guarda el frame, le dibuja los rectángulos y lo devuelve"""
        """Reads the camera, saves the frame, paints the rectangles and returns it"""
        ret, frame = self.cap.read()
        if not ret:
            return None, None, []
        
        if rotate:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        self.actual_frame = frame.copy()
        elems = list(self.detected_elems)

        for elem in elems:
            text = elem["data"]
            qr = elem["qr_obj"]
            dots = qr.polygon
            
            color = (0, 255, 0) if elem["type"] == "number" else (0, 255, 255)
            prefix = t("overlay_num_prefix") if elem["type"] == "number" else ""

            if len(dots) == 4:
                pts = np.array(dots, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], True, color, 3)
            else:
                rect = qr.rect
                cv2.rectangle(frame, (rect.left, rect.top), (rect.left + rect.width, rect.top + rect.height), color, 3)
            
            x_text = qr.rect.left
            y_text = max(0, qr.rect.top - 10) 
            cv2.putText(frame, f"{prefix}{text}", (x_text, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame, frame_rgb, [elem["data"] for elem in elems]
    
    @staticmethod
    def _group_into_rows(elems, row_threshold=50):
        """Agrupa los elementos en filas por posición vertical, ordenando cada fila por posición horizontal"""
        """Groups the elements into rows by vertical position, sorting each row by horizontal position"""
        rows = []
        act_row = []
        top_reference = -1

        for elem in elems:
            if top_reference == -1:
                top_reference = elem["top"]
                act_row.append(elem)
            elif abs(elem["top"] - top_reference) < row_threshold:
                act_row.append(elem)
            else:
                act_row.sort(key=lambda obj: obj["left"])
                rows.append(act_row)
                act_row = [elem]
                top_reference = elem["top"]

        if act_row:
            act_row.sort(key=lambda obj: obj["left"])
            rows.append(act_row)

        return rows

    def get_command_matrix(self):
        """Devuelve la matriz de commandos"""
        """Returns the command matrix"""
        elems = list(self.detected_elems)
        elems.sort(key=lambda obj: obj["top"])
        
        rows = self._group_into_rows(elems)
            
        matrix = []
        if rows:
            min_left = min(f[0]["left"] for f in rows)
            column_width = 90 
            
            for row in rows:
                num_indent = max(0, int(round((row[0]["left"] - min_left) / column_width)))
                strings_row = [""] * num_indent
                for elem in row:
                    strings_row.append(elem["data"])
                matrix.append(strings_row)
                
        return matrix
        
    def check_overflow(self):
        """Comprueba si hay desbordamiento"""
        """Checks if there is overflow"""
        if self.actual_frame is None: return None
        frame_height, frame_width, _ = self.actual_frame.shape
        elems = list(self.detected_elems)

        if not elems: return None

        right_margin = frame_width - 200
        down_margin = frame_height - 200

        elems.sort(key=lambda obj: obj["top"])
        rows = self._group_into_rows(elems)

        right_links = []
        down_link = None

        for row in rows:
            last_block = row[-1]
            if last_block["left"] + last_block["qr_obj"].rect.width > right_margin:
                right_links.append(last_block["data"])

        if rows:
            last_row = rows[-1]
            first_block = last_row[0]
            if first_block["top"] + first_block["qr_obj"].rect.height > down_margin:
                down_link = first_block["data"]

        if not (right_links or down_link):
            return None

        return {"right": right_links, "down": [down_link] if down_link else []}

    def free_camera(self):
        """Libera la camara"""
        """Releases the camera"""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    def start_camera(self, camera_index=None):
        """Enciende la camara"""
        """Starts the camera"""
        if camera_index is not None:
            self.camera_index = camera_index
            
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    def take_photo(self, frame, dest_path):
        """Hace una foto del frame y la guarda"""
        """Makes a photo of the frame and saves it"""
        cv2.imwrite(dest_path, frame)

    def get_photo(self, origin_path):
        """Coge el frame guardad"""
        """Gets the saved frame"""
        return cv2.imread(origin_path)
    
    def free(self):
        """Libera la camara"""
        """Releases the camera"""
        if self.cap is not None:
            self.cap.release()