import os
import qrcode
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

class QRManager:
    
    @staticmethod
    def generate_pdf(elems, size_mm, final_pdf_dir, workspace_dir):
        """
            Genera los QRs y los empaqueta en un PDF y
            devuelve la ruta absoluta del PDF generado
        """
        """
            Generate the QR's, packs them in a PDF and
            return the absolute path of the PDF
        """
        qrcodes_dir = os.path.join(workspace_dir, "outputs", "qrcodes", "dinamicos")
        os.makedirs(qrcodes_dir, exist_ok=True)
        
        images_list = []
        
        for i, text in enumerate(elems):
            img_dir = os.path.join(qrcodes_dir, f"qr_temp_{i}.png")
            
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(text)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            text_space = 40
            final_img = Image.new('RGB', (img_qr.width, img_qr.height + text_space), 'white')
            final_img.paste(img_qr, (0, 0))
            draw = ImageDraw.Draw(final_img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except IOError:
                font = ImageFont.load_default()
                
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            pos_x = (img_qr.width - text_w) / 2
            pos_y = img_qr.height + 5
            draw.text((pos_x, pos_y), text, fill="black", font=font)
            
            final_img.save(img_dir)
            images_list.append(img_dir)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        x_start, y_start, margin = 10, 10, 10
        limit_x, limit_y = 200, 270 
        x, y = x_start, y_start
        
        for img_path in images_list:
            pdf.image(img_path, x=x, y=y, w=size_mm)
            x += size_mm + margin
            if (x + size_mm) > limit_x: 
                x = x_start
                y += size_mm + margin + 10 
            if (y + size_mm) > limit_y:
                pdf.add_page()
                x, y = x_start, y_start
                
        pdf.output(final_pdf_dir)
        
        for img_path in images_list:
            try:
                os.remove(img_path)
            except:
                pass
                
        return final_pdf_dir