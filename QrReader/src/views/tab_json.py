from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QComboBox, QFrame)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
import os

class BuscadorAutoLimpiable(QLineEdit):
    def mousePressEvent(self, event):
        self.clear()                    
        super().mousePressEvent(event)  

class TabJSON(QWidget):
    def __init__(self, json_ctrl, assets_dir):
        super().__init__()
        self.json_ctrl = json_ctrl
        self.icons_dir = os.path.join(assets_dir, "icons")
        
        self.editando_actualmente = False
        self.llave_original = None

        self._setup_ui()
        self._cargar_lista()

    def showEvent(self, event):
        self._cargar_lista()
        super().showEvent(event)

    def _setup_ui(self):
        layout_principal = QHBoxLayout(self)

        # PANEL IZQUIERDO: FORMULARIO
        panel_form = QFrame()
        layout_form = QVBoxLayout(panel_form)
        layout_form.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.lbl_titulo = QLabel("Añadir Nuevo Bloque")
        self.lbl_titulo.setObjectName("titulo_seccion")
        layout_form.addWidget(self.lbl_titulo)

        layout_form.addWidget(QLabel("Texto del QR:"))
        self.entry_nombre = QLineEdit()
        self.entry_nombre.setPlaceholderText("ej: encender leds")
        layout_form.addWidget(self.entry_nombre)

        layout_form.addWidget(QLabel("Código Python:"))
        self.entry_codigo = QLineEdit()
        self.entry_codigo.setPlaceholderText("ej: display.show")
        layout_form.addWidget(self.entry_codigo)

        layout_form.addWidget(QLabel("Tipo de Nodo:"))
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems(["funcion", "valor", "control", "sujeto", "metodo", "operador_logico"])
        layout_form.addWidget(self.cb_tipo)

        layout_form.addWidget(QLabel("Argumentos:"))
        self.entry_args = QLineEdit("0")
        layout_form.addWidget(self.entry_args)

        layout_botones = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar Bloque")
        self.btn_guardar.setObjectName("btn_guardar")
        self.btn_guardar.clicked.connect(self.accion_guardar)
        layout_botones.addWidget(self.btn_guardar)
        
        self.btn_cancelar = QPushButton("Cancelar Edición")
        self.btn_cancelar.setObjectName("btn_cancelar_edicion")
        self.btn_cancelar.clicked.connect(self._reset_formulario)
        self.btn_cancelar.hide() 
        layout_botones.addWidget(self.btn_cancelar)
        
        layout_form.addLayout(layout_botones)
        self.lbl_estado = QLabel("")
        layout_form.addWidget(self.lbl_estado)
        layout_principal.addWidget(panel_form, stretch=1)

        # PANEL DERECHO: LISTA
        panel_lista = QFrame()
        layout_lista = QVBoxLayout(panel_lista)
        
        lbl_lista = QLabel("Bloques Actuales en Memoria")
        lbl_lista.setObjectName("titulo_seccion")
        layout_lista.addWidget(lbl_lista)

        layout_buscador = QHBoxLayout()
        layout_buscador.addWidget(QLabel("Buscar:"))
        self.buscador = BuscadorAutoLimpiable()
        self.buscador.setPlaceholderText("Escribe para filtrar bloques...")
        self.buscador.textChanged.connect(self._filtrar_tabla)
        layout_buscador.addWidget(self.buscador)

        self.btn_borrar_sel = QPushButton()
        self.btn_borrar_sel.setIcon(QIcon(os.path.join(self.icons_dir, "bin.png")))
        self.btn_borrar_sel.setObjectName("btn_eliminar_masivo")
        self.btn_borrar_sel.setEnabled(False) 
        self.btn_borrar_sel.clicked.connect(self.accion_eliminar_seleccionados)
        layout_buscador.addWidget(self.btn_borrar_sel)
        
        layout_lista.addLayout(layout_buscador)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4) 
        self.tabla.setHorizontalHeaderLabels(["Bloque -> Traducción", "Editar", "Borrar", "Sel"])
        self.tabla.verticalHeader().setDefaultSectionSize(40)
        self.tabla.itemChanged.connect(self._verificar_seleccion)
        
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)          
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) 
        
        layout_lista.addWidget(self.tabla)
        layout_principal.addWidget(panel_lista, stretch=2)

    def _filtrar_tabla(self, texto):
        texto = texto.lower()
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 0) 
            if item:
                mostrar = texto in item.text().lower()
                self.tabla.setRowHidden(fila, not mostrar)

    def _verificar_seleccion(self):
        hay_seleccion = False
        for fila in range(self.tabla.rowCount()):
            item_chk = self.tabla.item(fila, 3) 
            if item_chk and item_chk.checkState() == Qt.CheckState.Checked:
                hay_seleccion = True
                break
        self.btn_borrar_sel.setEnabled(hay_seleccion)

    def accion_eliminar_seleccionados(self):
        claves_a_borrar = []
        for fila in range(self.tabla.rowCount()):
            item_chk = self.tabla.item(fila, 3) 
            if item_chk and item_chk.checkState() == Qt.CheckState.Checked:
                claves_a_borrar.append(item_chk.data(Qt.ItemDataRole.UserRole))
                
        if not claves_a_borrar: return

        exitos = 0
        for clave in claves_a_borrar:
            try:
                self.json_ctrl.eliminar_bloque(clave)
                if self.editando_actualmente and self.llave_original == clave:
                    self._reset_formulario()
                exitos += 1
            except Exception:
                pass

        if exitos > 0:
            self._cargar_lista()
            self.lbl_estado.setText(f"Se han eliminado {exitos} bloques seleccionados.")

    def _cargar_lista(self):
        self.tabla.blockSignals(True) 
        self.tabla.setRowCount(0)
        bloques = self.json_ctrl.obtener_bloques()
        self.tabla.setRowCount(len(bloques))

        for fila, bloque in enumerate(bloques):
            clave = bloque["clave"]
            info = bloque["info"]
            
            texto = f"{clave} -> {info.get('codigo', '')}"
            item = QTableWidgetItem(texto)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(fila, 0, item) 

            btn_edit = QPushButton()
            btn_edit.setIcon(QIcon(os.path.join(self.icons_dir, "edit.png")))
            btn_edit.setObjectName("btn_tabla_editar")
            btn_edit.clicked.connect(lambda checked, c=clave, i=info: self._cargar_edicion(c, i))
            self.tabla.setCellWidget(fila, 1, btn_edit) 

            btn_del = QPushButton()
            btn_del.setIcon(QIcon(os.path.join(self.icons_dir, "bin.png")))
            btn_del.setObjectName("btn_tabla_borrar")
            btn_del.clicked.connect(lambda checked, c=clave: self.accion_eliminar(c))
            self.tabla.setCellWidget(fila, 2, btn_del) 

            item_chk = QTableWidgetItem()
            item_chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_chk.setCheckState(Qt.CheckState.Unchecked)
            item_chk.setData(Qt.ItemDataRole.UserRole, clave) 
            self.tabla.setItem(fila, 3, item_chk) 
            
        self.tabla.blockSignals(False)
        self._verificar_seleccion() 

        if self.buscador.text():
            self._filtrar_tabla(self.buscador.text())

    def _cargar_edicion(self, clave, info):
        self.editando_actualmente = True
        self.llave_original = clave
        
        self.lbl_titulo.setText(f"Editando: {clave}")
        self.btn_guardar.setText("Actualizar Bloque")
        self.btn_cancelar.show()

        self.entry_nombre.setText(clave)
        self.entry_codigo.setText(info.get("codigo", ""))
        self.cb_tipo.setCurrentText(info.get("tipo", "funcion"))
        self.entry_args.setText(str(info.get("args", "0")))

    def _reset_formulario(self):
        self.editando_actualmente = False
        self.llave_original = None
        self.lbl_titulo.setText("Añadir Nuevo Bloque")
        self.btn_guardar.setText("Guardar Bloque")
        self.btn_cancelar.hide()
        self.entry_nombre.clear()
        self.entry_codigo.clear()
        self.entry_args.setText("0")
        self.lbl_estado.setText("")

    def accion_guardar(self):
        nombre = self.entry_nombre.text().strip().lower()
        codigo = self.entry_codigo.text().strip()
        tipo = self.cb_tipo.currentText()
        
        try:
            args = int(self.entry_args.text().strip())
        except ValueError:
            args = 0
            
        if not nombre or not codigo:
            self.lbl_estado.setText("Error: El nombre y el código son obligatorios.")
            return

        nuevo_nodo = {"codigo": codigo, "tipo": tipo}
        if tipo in ["funcion", "metodo"]: nuevo_nodo["args"] = args
        if tipo == "sujeto": nuevo_nodo["clase"] = "general"

        nombre_antiguo = self.llave_original if self.editando_actualmente else None
        
        try:
            self.json_ctrl.guardar_bloque(nombre_antiguo, nombre, nuevo_nodo)
            self.lbl_estado.setText(f"¡Bloque '{nombre}' guardado con éxito!")
            self._reset_formulario()
            self._cargar_lista()
        except Exception as e:
            self.lbl_estado.setText(f"Error al guardar: {e}")

    def accion_eliminar(self, clave):
        try:
            self.json_ctrl.eliminar_bloque(clave)
            self._cargar_lista()
            if self.editando_actualmente and self.llave_original == clave:
                self._reset_formulario()
            self.lbl_estado.setText(f"Bloque '{clave}' eliminado.")
        except Exception as e:
            self.lbl_estado.setText(f"Error al eliminar: {e}")