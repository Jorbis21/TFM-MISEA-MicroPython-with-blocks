from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QFileDialog)
from PyQt6.QtCore import Qt
from views.widgets import AutoCleanSearch
from utils.strings import t

class TabQRs(QWidget):
    """Pestaña de generación de QRs: tabla con la cantidad deseada de cada bloque, y botón para generar el PDF de impresión con el tamaño elegido"""
    """QR-generation tab: table with the desired quantity of each block, and a button to generate the print-ready PDF at the chosen size"""

    def __init__(self, qr_ctrl):
        """Deja la tabla preparada, sin cargar los bloques todavía (se cargan la primera vez que se muestra esta pestaña)"""
        """Leaves the table ready, without loading the blocks yet (they get loaded the first time this tab is shown)"""
        super().__init__()
        self.qr_ctrl = qr_ctrl
        self.qr_entries = {}

        self._setup_ui()
        self.load_qrs_list()

    def _setup_ui(self):
        """Monta la interfaz"""
        """Setup the interface"""
        main_layout = QVBoxLayout(self)

        layout_top = QHBoxLayout()
        lbl_title = QLabel(t("title_qr_print"))
        lbl_title.setObjectName("titulo_seccion")
        layout_top.addWidget(lbl_title)
        layout_top.addStretch()
        
        self.active_btn = QPushButton(t("btn_show_active"))
        self.active_btn.setObjectName("btn_filter_actives")
        self.active_btn.setCheckable(True) 
        self.active_btn.toggled.connect(self.action_filter_actives)
        layout_top.addWidget(self.active_btn)

        all_one_btn = QPushButton(t("btn_all_one"))
        all_one_btn.setObjectName("all_one_btn")
        all_one_btn.clicked.connect(self.action_all_one)
        layout_top.addWidget(all_one_btn)

        all_cero_btn = QPushButton(t("btn_clear_zero"))
        all_cero_btn.setObjectName("all_cero_btn")
        all_cero_btn.clicked.connect(self.action_all_cero)
        layout_top.addWidget(all_cero_btn)

        main_layout.addLayout(layout_top)

        layout_search = QHBoxLayout()
        layout_search.addWidget(QLabel(t("lbl_search_block")))
        self.search = AutoCleanSearch()
        self.search.setPlaceholderText(t("placeholder_search"))
        self.search.textChanged.connect(self._filter_table)
        layout_search.addWidget(self.search)
        main_layout.addLayout(layout_search)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([t("table_header_block_name"), "-", t("table_header_quantity"), "+"])
        self.table.verticalHeader().setDefaultSectionSize(40)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        main_layout.addWidget(self.table)

        layout_bottom = QHBoxLayout()
        layout_bottom.addWidget(QLabel(t("lbl_size_cm")))
        
        self.entry_size = QLineEdit("2.5")
        self.entry_size.setFixedWidth(60)
        self.entry_size.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_bottom.addWidget(self.entry_size)

        self.generate_pdf_btn = QPushButton(t("btn_generate_pdf"))
        self.generate_pdf_btn.setObjectName("generate_pdf_btn")
        self.generate_pdf_btn.clicked.connect(self.action_generate_pdf)
        layout_bottom.addWidget(self.generate_pdf_btn)
        
        self.lbl_state_qr = QLabel("")
        layout_bottom.addWidget(self.lbl_state_qr)
        layout_bottom.addStretch()

        main_layout.addLayout(layout_bottom)

    def showEvent(self, event):
        """Evento de mostrar la ventana"""
        """Show window event"""
        self.load_qrs_list()
        super().showEvent(event)

    def action_filter_actives(self, active):
        """Accion para mostrar todos o los que tienen uno o mas"""
        """Action to show all or the ones with one or more"""
        if active:
            self.active_btn.setText(t("btn_show_all"))
            for row in range(self.table.rowCount()):
                entry = self.table.cellWidget(row, 2)
                quant = self._safe_int(entry.text()) if entry else 0
                self.table.setRowHidden(row, quant == 0)
        else:
            self.active_btn.setText(t("btn_show_active"))
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            if self.search.text():
                self._filter_table(self.search.text())

    def load_qrs_list(self):
        """Carga la lista de QR's"""
        """Loads the QR list"""
        previous_quantities = {}
        for k, v in self.qr_entries.items():
            previous_quantities[k] = v.text()

        self.table.setRowCount(0)
        self.qr_entries.clear()

        blocks = self.qr_ctrl.get_symbols()
        self.table.setRowCount(len(blocks))

        for row, block in enumerate(blocks):
            item_name = QTableWidgetItem(block.capitalize())
            item_name.setFlags(Qt.ItemFlag.ItemIsEnabled) 
            self.table.setItem(row, 0, item_name)
            
            btn_minus = QPushButton("-")
            btn_minus.setObjectName("btn_cont")
            btn_minus.setFixedWidth(30)
            
            recovered_value = previous_quantities.get(block, "0")
            entry_cant = QLineEdit(recovered_value)
            entry_cant.setFixedWidth(50)
            entry_cant.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            btn_plus = QPushButton("+")
            btn_plus.setObjectName("btn_cont")
            btn_plus.setFixedWidth(30)

            btn_minus.clicked.connect(lambda checked, e=entry_cant: self._modify_quantity(e, -1))
            btn_plus.clicked.connect(lambda checked, e=entry_cant: self._modify_quantity(e, 1))

            self.table.setCellWidget(row, 1, btn_minus)
            self.table.setCellWidget(row, 2, entry_cant)
            self.table.setCellWidget(row, 3, btn_plus)
            
            self.qr_entries[block] = entry_cant
            
        if self.active_btn.isChecked():
            self.action_filter_actives(True)
        elif self.search.text():
            self._filter_table(self.search.text())
            
        self.lbl_state_qr.setText(t("list_updated"))

    def action_all_one(self):
        """Pone todos los elementos a uno"""
        """Sets all the elems to one"""
        for entry in self.qr_entries.values():
            entry.setText("1")
        if self.active_btn.isChecked():
            self.action_filter_actives(True)

    def action_all_cero(self):
        """Pone todos los elementos a cero"""
        """Sets all the elems to cero"""
        for entry in self.qr_entries.values():
            entry.setText("0")
        if self.active_btn.isChecked():
            self.action_filter_actives(True)

    def action_generate_pdf(self):
        """Genera el pdf con los QR's"""
        """Generates the pdf with the selected QR's"""
        try:
            size_cm = float(self.entry_size.text().strip())
            size_mm = round(size_cm * 10)
        except ValueError:
            self.lbl_state_qr.setText(t("error_invalid_size"))
            return

        elems_to_generate = []
        for block, entry in self.qr_entries.items():
            cantidad = self._safe_int(entry.text())
            if cantidad > 0:
                elems_to_generate.extend([block] * cantidad)
                
        if not elems_to_generate:
            self.lbl_state_qr.setText(t("error_no_quantity"))
            return

        dest_dir, _ = QFileDialog.getSaveFileName(
            self,
            t("dialog_save_pdf_title"),
            t("dialog_pdf_default_name"), 
            t("dialog_pdf_filter")
        )

        if not dest_dir:
            self.lbl_state_qr.setText(t("save_cancelled"))
            return

        self.generate_pdf_btn.setEnabled(False)

        def update_state(msg):
            """Muestra el mensaje de progreso recibido desde la generación del PDF"""
            """Shows the progress message received from the PDF generation"""
            self.lbl_state_qr.setText(msg)

        def on_finished():
            """Reactiva el botón de generar, permitiendo lanzar otra generación"""
            """Re-enables the generate button, allowing another generation to be started"""
            self.generate_pdf_btn.setEnabled(True)

        self.qr_ctrl.generate_pdf(elems_to_generate, size_mm, dest_dir, update_state, on_finished)

    @staticmethod
    def _safe_int(text, default=0):
        """Convierte un texto a entero, devolviendo un valor por defecto si no se puede"""
        """Converts a text to an integer, returning a default value if it can't be done"""
        try:
            return int(text.strip())
        except ValueError:
            return default

    def _modify_quantity(self, entry, delta):
        """Modifica la cantidad del elemento"""
        """Modifies the quantity of the element"""
        new_val = max(0, self._safe_int(entry.text()) + delta)
        entry.setText(str(new_val))
        
        if new_val == 0 and self.active_btn.isChecked():
            self.action_filter_actives(True)

    def _filter_table(self, text):
        """Filtra la tabla"""
        """Filters the table"""
        text = text.lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                show = text in item.text().lower()
                self.table.setRowHidden(row, not show)