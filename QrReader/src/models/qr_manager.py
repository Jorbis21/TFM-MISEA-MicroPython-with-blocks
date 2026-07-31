import os
import qrcode
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

class QRManager:
    """Motor encargado de la generación de imágenes QR y compilación de PDFs."""
    
    @staticmethod
    def generar_pdf_impresion(elementos, tamano_mm, workspace_dir):
        """
        Genera los QRs y los empaqueta en un PDF.
        Devuelve la ruta absoluta del PDF generado.
        """
        qrcodes_dir = os.path.join(workspace_dir, "outputs", "qrcodes", "dinamicos")
        os.makedirs(qrcodes_dir, exist_ok=True)
        
        lista_imagenes = []
        
        # 1. Generar imágenes individuales
        for i, texto in enumerate(elementos):
            ruta_img = os.path.join(qrcodes_dir, f"qr_temp_{i}.png")
            
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(texto)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            espacio_texto = 40
            img_final = Image.new('RGB', (img_qr.width, img_qr.height + espacio_texto), 'white')
            img_final.paste(img_qr, (0, 0))
            draw = ImageDraw.Draw(img_final)
            
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except IOError:
                font = ImageFont.load_default()
                
            bbox = draw.textbbox((0, 0), texto, font=font)
            text_w = bbox[2] - bbox[0]
            pos_x = (img_qr.width - text_w) / 2
            pos_y = img_qr.height + 5
            draw.text((pos_x, pos_y), texto, fill="black", font=font)
            
            img_final.save(ruta_img)
            lista_imagenes.append(ruta_img)

        # 2. Empaquetar en PDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        x_start, y_start, margen = 10, 10, 10
        limite_x, limite_y = 200, 270 
        x, y = x_start, y_start
        
        for img_path in lista_imagenes:
            pdf.image(img_path, x=x, y=y, w=tamano_mm)
            x += tamano_mm + margen
            if (x + tamano_mm) > limite_x: 
                x = x_start
                y += tamano_mm + margen + 10 
            if (y + tamano_mm) > limite_y:
                pdf.add_page()
                x, y = x_start, y_start
                
        ruta_pdf_final = os.path.join(workspace_dir, "outputs", "qrs_impresion.pdf")
        pdf.output(ruta_pdf_final)
        
        # 3. Limpieza de memoria temporal
        for img_path in lista_imagenes:
            try:
                os.remove(img_path)
            except:
                pass
                
        return ruta_pdf_final