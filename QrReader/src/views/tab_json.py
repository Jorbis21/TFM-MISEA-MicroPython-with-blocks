import os

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QComboBox, QFrame)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from views.widgets import AutoCleanSearch
from utils.strings import t

class TabJSON(QWidget):
    """Pestaña de edición del diccionario de bloques: formulario para crear/editar un bloque, y tabla con todos los existentes, con búsqueda y borrado individual o múltiple"""
    """Dictionary-editing tab: form to create/edit a block, and a table with all the existing ones, with search and individual or multiple deletion"""

    def __init__(self, json_ctrl, assets_dir):
        """Monta el formulario y la tabla, y deja preparada la carga del diccionario la primera vez que se muestre esta pestaña"""
        """Builds the form and the table, and prepares loading the dictionary the first time this tab is shown"""
        super().__init__()
        self.json_ctrl = json_ctrl
        self.icons_dir = os.path.join(assets_dir, "icons")
        
        self.editing = False
        self.original_key = None

        self._setup_ui()
        self._load_list()

    def _setup_ui(self):
        """Monta la interfaz"""
        """Setup the interface"""
        main_layout = QHBoxLayout(self)

        panel_form = QFrame()
        layout_form = QVBoxLayout(panel_form)
        layout_form.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.lbl_title = QLabel(t("title_add_block"))
        self.lbl_title.setObjectName("titulo_seccion")
        layout_form.addWidget(self.lbl_title)

        layout_form.addWidget(QLabel(t("lbl_qr_text")))
        self.entry_name = QLineEdit()
        self.entry_name.setPlaceholderText(t("placeholder_qr_text"))
        layout_form.addWidget(self.entry_name)

        layout_form.addWidget(QLabel(t("lbl_python_code")))
        self.entry_code = QLineEdit()
        self.entry_code.setPlaceholderText(t("placeholder_python_code"))
        layout_form.addWidget(self.entry_code)

        layout_form.addWidget(QLabel(t("lbl_node_type")))
        self.cb_type = QComboBox()
        self.cb_type.addItems(["function", "value", "control", "subject", "method", "logic_operator"])
        layout_form.addWidget(self.cb_type)

        layout_form.addWidget(QLabel(t("lbl_arguments")))
        self.entry_args = QLineEdit("0")
        layout_form.addWidget(self.entry_args)

        btns_layout = QHBoxLayout()
        self.save_btn = QPushButton(t("btn_save_block"))
        self.save_btn.setObjectName("save_btn")
        self.save_btn.clicked.connect(self.action_save)
        btns_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton(t("btn_cancel_edit"))
        self.cancel_btn.setObjectName("cancel_btn_edit")
        self.cancel_btn.clicked.connect(self._reset_form)
        self.cancel_btn.hide() 
        btns_layout.addWidget(self.cancel_btn)
        
        layout_form.addLayout(btns_layout)
        self.lbl_state = QLabel("")
        layout_form.addWidget(self.lbl_state)
        main_layout.addWidget(panel_form, stretch=1)

        panel_list = QFrame()
        layout_list = QVBoxLayout(panel_list)
        
        lbl_lista = QLabel(t("title_blocks_in_memory"))
        lbl_lista.setObjectName("titulo_seccion")
        layout_list.addWidget(lbl_lista)

        layout_search = QHBoxLayout()
        layout_search.addWidget(QLabel(t("lbl_search")))
        self.search = AutoCleanSearch()
        self.search.setPlaceholderText(t("placeholder_search_blocks"))
        self.search.textChanged.connect(self._filter_table)
        layout_search.addWidget(self.search)

        self.delete_sel_btn = QPushButton()
        self.delete_sel_btn.setIcon(QIcon(os.path.join(self.icons_dir, "bin.png")))
        self.delete_sel_btn.setObjectName("masive_delete_btn")
        self.delete_sel_btn.setEnabled(False) 
        self.delete_sel_btn.clicked.connect(self.action_delete_selected)
        layout_search.addWidget(self.delete_sel_btn)
        
        layout_list.addLayout(layout_search)

        self.table = QTableWidget()
        self.table.setColumnCount(4) 
        self.table.setHorizontalHeaderLabels([t("table_header_block_translation"), t("table_header_edit"), t("table_header_delete"), t("table_header_sel")])
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.itemChanged.connect(self._verify_selection)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)          
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) 
        
        layout_list.addWidget(self.table)
        main_layout.addWidget(panel_list, stretch=2)

    def showEvent(self, event):
        """Evento de mostrar la ventana"""
        """Show window event"""
        self._load_list()
        super().showEvent(event)

    def action_save(self):
        """Accion de guardar los bloques modificados"""
        """Save modified blocks action"""
        name = self.entry_name.text().strip().lower()
        code = self.entry_code.text().strip()
        type = self.cb_type.currentText()
        
        try:
            args = int(self.entry_args.text().strip())
        except ValueError:
            args = 0
            
        if not name or not code:
            self.lbl_state.setText(t("error_name_code_required"))
            return

        new_node = {"code": code, "type": type}
        if type in ["function", "method"]: new_node["args"] = args
        if type == "subject": new_node["class"] = "general"

        old_node = self.original_key if self.editing else None
        
        try:
            self.json_ctrl.save_block(old_node, name, new_node)
            self.lbl_state.setText(t("block_saved_success", name=name))
            self._reset_form()
            self._load_list()
        except Exception as e:
            self.lbl_state.setText(t("error_saving", error=e))

    def action_delete(self, key):
        """Accion de borrar un bloque"""
        """Delete one block action"""
        try:
            self.json_ctrl.delete_block(key)
            self._load_list()
            if self.editing and self.original_key == key:
                self._reset_form()
            self.lbl_state.setText(t("block_deleted", name=key))
        except Exception as e:
            self.lbl_state.setText(t("error_deleting", error=e))

    def action_delete_selected(self):
        """Accion de borrar bloques seleccionados"""
        """Delete selected blocks action"""
        keys_to_delete = []
        for row in range(self.table.rowCount()):
            item_chk = self.table.item(row, 3) 
            if item_chk and item_chk.checkState() == Qt.CheckState.Checked:
                keys_to_delete.append(item_chk.data(Qt.ItemDataRole.UserRole))
                
        if not keys_to_delete: return

        successes = 0
        failures = []
        for key in keys_to_delete:
            try:
                self.json_ctrl.delete_block(key)
                if self.editing and self.original_key == key:
                    self._reset_form()
                successes += 1
            except Exception as e:
                failures.append(f"{key} ({e})")

        if successes > 0:
            self._load_list()

        if not failures:
            self.lbl_state.setText(t("blocks_deleted_success", count=successes))
        elif successes > 0:
            self.lbl_state.setText(t("blocks_deleted_partial", count=successes, failures=", ".join(failures)))
        else:
            self.lbl_state.setText(t("blocks_deleted_none", failures=", ".join(failures)))


    def _filter_table(self, text):
        """Filtra la tabla"""
        """Filters the table"""
        text = text.lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0) 
            if item:
                show = text in item.text().lower()
                self.table.setRowHidden(row, not show)

    def _verify_selection(self):
        """Verifica la seleccion"""
        """Verifies the selection"""
        selection = False
        for row in range(self.table.rowCount()):
            item_chk = self.table.item(row, 3) 
            if item_chk and item_chk.checkState() == Qt.CheckState.Checked:
                selection = True
                break
        self.delete_sel_btn.setEnabled(selection)

    def _load_list(self):
        """Carga la lista"""
        """Loads the list"""
        self.table.blockSignals(True) 
        self.table.setRowCount(0)
        blocks = self.json_ctrl.get_blocks()
        self.table.setRowCount(len(blocks))

        for row, block in enumerate(blocks):
            key = block["key"]
            info = block["info"]
            
            text = f"{key} -> {info.get('code', '')}"
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 0, item) 

            btn_edit = QPushButton()
            btn_edit.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
            btn_edit.setObjectName("btn_table_edit")
            btn_edit.clicked.connect(lambda checked, c=key, i=info: self._load_edit(c, i))
            self.table.setCellWidget(row, 1, btn_edit) 

            btn_del = QPushButton()
            btn_del.setIcon(QIcon(os.path.join(self.icons_dir, "bin.png")))
            btn_del.setObjectName("btn_table_del")
            btn_del.clicked.connect(lambda checked, c=key: self.action_delete(c))
            self.table.setCellWidget(row, 2, btn_del) 

            item_chk = QTableWidgetItem()
            item_chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_chk.setCheckState(Qt.CheckState.Unchecked)
            item_chk.setData(Qt.ItemDataRole.UserRole, key) 
            self.table.setItem(row, 3, item_chk) 
            
        self.table.blockSignals(False)
        self._verify_selection() 

        if self.search.text():
            self._filter_table(self.search.text())

    def _load_edit(self, key, info):
        """Carga el modo edicion"""
        """Load edition mode"""
        self.editing = True
        self.original_key = key
        
        self.lbl_title.setText(t("title_editing", name=key))
        self.save_btn.setText(t("btn_update_block"))
        self.cancel_btn.show()

        self.entry_name.setText(key)
        self.entry_code.setText(info.get("code", ""))
        self.cb_type.setCurrentText(info.get("type", "function"))
        self.entry_args.setText(str(info.get("args", "0")))

    def _reset_form(self):
        """Resetea el form"""
        """Resets the form"""
        self.editing = False
        self.original_key = None
        self.lbl_title.setText(t("title_add_block"))
        self.save_btn.setText(t("btn_save_block"))
        self.cancel_btn.hide()
        self.entry_name.clear()
        self.entry_code.clear()
        self.cb_type.setCurrentIndex(0)
        self.entry_args.setText("0")
        self.lbl_state.setText("")