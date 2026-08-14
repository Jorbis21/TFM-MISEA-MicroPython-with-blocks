import os
import uuid
import qrcode
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

class QRManager:

    # Alternativas a "arial.ttf" (solo existe tal cual en Windows) para que la
    # etiqueta bajo cada QR tenga un tamaño razonable en Linux/Mac tambien.
    # Alternatives to "arial.ttf" (which only exists as-is on Windows) so the
    # label under each QR has a reasonable size on Linux/Mac too.
    _FONT_CANDIDATES = [
        "arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    @staticmethod
    def _load_font(size=16):
        for path in QRManager._FONT_CANDIDATES:
            try:
                return ImageFont.truetype(path, size)
            except IOError:
                continue
        return ImageFont.load_default()

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
        # Carpeta unica por llamada: evita que dos generaciones simultaneas
        # (p. ej. un doble clic accidental) se pisen los ficheros temporales.
        # Unique folder per call: prevents two simultaneous generations
        # (e.g. an accidental double click) from stepping on each other's temp files.
        qrcodes_dir = os.path.join(workspace_dir, "outputs", "qrcodes", "dinamicos", uuid.uuid4().hex)
        os.makedirs(qrcodes_dir, exist_ok=True)

        font = QRManager._load_font(16)

        images_list = []

        for i, text in enumerate(elems):
            img_path = os.path.join(qrcodes_dir, f"qr_temp_{i}.png")

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(text)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')

            text_space = 40
            final_img = Image.new('RGB', (img_qr.width, img_qr.height + text_space), 'white')
            final_img.paste(img_qr, (0, 0))
            draw = ImageDraw.Draw(final_img)

            label = text
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]

            if text_w > img_qr.width:
                while len(label) > 1 and text_w > img_qr.width:
                    label = label[:-1]
                    bbox = draw.textbbox((0, 0), label + "...", font=font)
                    text_w = bbox[2] - bbox[0]
                label = label + "..."

            pos_x = (img_qr.width - text_w) / 2
            pos_y = img_qr.height + 5
            draw.text((pos_x, pos_y), label, fill="black", font=font)

            final_img.save(img_path)
            images_list.append(img_path)

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

        try:
            pdf.output(final_pdf_dir)
        finally:
            for img_path in images_list:
                try:
                    os.remove(img_path)
                except OSError:
                    pass
            try:
                os.rmdir(qrcodes_dir)
            except OSError:
                pass

        return final_pdf_dir