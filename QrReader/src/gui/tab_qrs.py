import threading
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
from utils.qr_manager import QRManager

class TabQRs(QWidget):
    def __init__(self, workspace_dir, traductor):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.traductor = traductor
        self.entradas_qr = {}

        self._setup_ui()
        self.cargar_lista_qrs()

    def _setup_ui(self):
        layout_principal = QVBoxLayout(self)

        # ==========================================
        # BARRA SUPERIOR
        # ==========================================
        layout_top = QHBoxLayout()
        lbl_titulo = QLabel("Mesa de Impresión de Códigos QR")
        lbl_titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout_top.addWidget(lbl_titulo)
        layout_top.addStretch()

        btn_refrescar = QPushButton("↻ Refrescar Lista")
        btn_refrescar.setStyleSheet("background-color: #0052cc; color: white; padding: 8px;")
        btn_refrescar.clicked.connect(self.cargar_lista_qrs)
        layout_top.addWidget(btn_refrescar)

        btn_todos_uno = QPushButton("Todos a 1")
        btn_todos_uno.setStyleSheet("background-color: #8E44AD; color: white; padding: 8px;")
        btn_todos_uno.clicked.connect(self.accion_todos_a_uno)
        layout_top.addWidget(btn_todos_uno)

        btn_todos_cero = QPushButton("Limpiar a 0")
        btn_todos_cero.setStyleSheet("background-color: #E74C3C; color: white; padding: 8px;")
        btn_todos_cero.clicked.connect(self.accion_todos_a_cero)
        layout_top.addWidget(btn_todos_cero)

        layout_principal.addLayout(layout_top)

        # --- NUEVO: BARRA DE BÚSQUEDA ---
        layout_buscador = QHBoxLayout()
        layout_buscador.addWidget(QLabel("🔍 Buscar bloque:"))
        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Escribe para filtrar...")
        self.buscador.textChanged.connect(self._filtrar_tabla)
        layout_buscador.addWidget(self.buscador)
        layout_principal.addLayout(layout_buscador)
        # --------------------------------

        # ==========================================
        # TABLA DE BLOQUES
        # ==========================================
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Nombre del Bloque", "-", "Cantidad", "+"])
        
        # Ajuste de columnas
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # El nombre ocupa todo el espacio
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        layout_principal.addWidget(self.tabla)

        # ==========================================
        # CONTROLES INFERIORES
        # ==========================================
        layout_bottom = QHBoxLayout()
        layout_bottom.addWidget(QLabel("Tamaño (cm):"))
        
        self.entry_tamano = QLineEdit("5.0")
        self.entry_tamano.setFixedWidth(60)
        self.entry_tamano.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_bottom.addWidget(self.entry_tamano)

        btn_generar_pdf = QPushButton("Generar PDF de Impresión")
        btn_generar_pdf.setStyleSheet("background-color: #2FA572; color: white; font-weight: bold; padding: 8px;")
        btn_generar_pdf.clicked.connect(self.accion_generar_pdf_qrs)
        layout_bottom.addWidget(btn_generar_pdf)
        
        self.lbl_estado_qr = QLabel("")
        self.lbl_estado_qr.setStyleSheet("color: gray;")
        layout_bottom.addWidget(self.lbl_estado_qr)
        layout_bottom.addStretch()

        layout_principal.addLayout(layout_bottom)

    # --- NUEVA FUNCIÓN: FILTRADO EN TIEMPO REAL ---
    def _filtrar_tabla(self, texto):
        texto = texto.lower()
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 0)
            if item:
                mostrar = texto in item.text().lower()
                self.tabla.setRowHidden(fila, not mostrar)
    # ----------------------------------------------

    # =========================================================
    # LÓGICA DE INTERFAZ Y CANTIDADES
    # =========================================================
    def cargar_lista_qrs(self):
        self.tabla.setRowCount(0)
        self.entradas_qr.clear()

        bloques = sorted(self.traductor.tabla_simbolos.keys())
        self.tabla.setRowCount(len(bloques))

        for fila, bloque in enumerate(bloques):
            # 1. Nombre
            item_nombre = QTableWidgetItem(bloque.capitalize())
            item_nombre.setFlags(Qt.ItemFlag.ItemIsEnabled) # Solo lectura
            self.tabla.setItem(fila, 0, item_nombre)
            
            # 2. Botón -
            btn_menos = QPushButton("-")
            btn_menos.setFixedWidth(30)
            
            # 3. Entry cantidad
            entry_cant = QLineEdit("0")
            entry_cant.setFixedWidth(50)
            entry_cant.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 4. Botón +
            btn_mas = QPushButton("+")
            btn_mas.setFixedWidth(30)

            # Conectar botones
            btn_menos.clicked.connect(lambda checked, e=entry_cant: self._modificar_cantidad(e, -1))
            btn_mas.clicked.connect(lambda checked, e=entry_cant: self._modificar_cantidad(e, 1))

            # Añadir widgets a la tabla
            self.tabla.setCellWidget(fila, 1, btn_menos)
            self.tabla.setCellWidget(fila, 2, entry_cant)
            self.tabla.setCellWidget(fila, 3, btn_mas)
            
            self.entradas_qr[bloque] = entry_cant
            
        # Reaplicar filtro si ya había texto al refrescar
        if self.buscador.text():
            self._filtrar_tabla(self.buscador.text())
            
        self.lbl_estado_qr.setText("Lista actualizada desde memoria.")
        self.lbl_estado_qr.setStyleSheet("color: #569CD6;")

    def _modificar_cantidad(self, entry, delta):
        try:
            val = int(entry.text().strip())
        except ValueError:
            val = 0
        nuevo_val = max(0, val + delta)
        entry.setText(str(nuevo_val))

    def accion_todos_a_uno(self):
        for entry in self.entradas_qr.values():
            entry.setText("1")

    def accion_todos_a_cero(self):
        for entry in self.entradas_qr.values():
            entry.setText("0")

    # =========================================================
    # GENERACIÓN DE PDF
    # =========================================================
    def accion_generar_pdf_qrs(self):
        try:
            tamano_cm = float(self.entry_tamano.text().strip())
            tamano_mm = int(tamano_cm * 10)
        except ValueError:
            self.lbl_estado_qr.setText("Error: Tamaño inválido. Usa formato '5.0'")
            self.lbl_estado_qr.setStyleSheet("color: #FF4C4C;")
            return

        elementos_a_generar = []
        for bloque, entry in self.entradas_qr.items():
            try:
                cantidad = int(entry.text().strip())
                if cantidad > 0:
                    elementos_a_generar.extend([bloque] * cantidad)
            except ValueError:
                continue
                
        if not elementos_a_generar:
            self.lbl_estado_qr.setText("No has seleccionado ninguna cantidad.")
            self.lbl_estado_qr.setStyleSheet("color: #D4AC0D;")
            return

        self.lbl_estado_qr.setText("Generando imágenes y PDF...")
        self.lbl_estado_qr.setStyleSheet("color: #569CD6;")
        
        threading.Thread(target=self._tarea_generar_pdf, args=(elementos_a_generar, tamano_mm), daemon=True).start()

    def _tarea_generar_pdf(self, elementos_a_generar, tamano_mm):
        try:
            ruta_pdf = QRManager.generar_pdf_impresion(elementos_a_generar, tamano_mm, self.workspace_dir)
            self.lbl_estado_qr.setText(f"¡Éxito! PDF guardado en: {ruta_pdf}")
            self.lbl_estado_qr.setStyleSheet("color: #2FA572;")
        except Exception as e:
            self.lbl_estado_qr.setText(f"Error al generar PDF: {e}")
            self.lbl_estado_qr.setStyleSheet("color: #FF4C4C;")