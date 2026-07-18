from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QComboBox, QFrame)
from PyQt6.QtCore import Qt
from utils.json_manager import JsonManager

class BuscadorAutoLimpiable(QLineEdit):
    """Caja de texto que se vacía automáticamente al hacerle clic con el ratón."""
    def mousePressEvent(self, event):
        self.clear()                    
        super().mousePressEvent(event)  

class TabJSON(QWidget):
    def __init__(self, config_dir, traductor):
        super().__init__()
        self.traductor = traductor
        self.json_manager = JsonManager(config_dir)
        
        self.editando_actualmente = False
        self.llave_original = None

        self._setup_ui()
        self._cargar_lista()

    # --- NUEVO: RECARGA AUTOMÁTICA AL MOSTRAR LA PESTAÑA ---
    def showEvent(self, event):
        self._cargar_lista()
        super().showEvent(event)

    def _setup_ui(self):
        layout_principal = QHBoxLayout(self)

        # ==========================================
        # PANEL IZQUIERDO: FORMULARIO
        # ==========================================
        panel_form = QFrame()
        layout_form = QVBoxLayout(panel_form)
        layout_form.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.lbl_titulo = QLabel("Añadir Nuevo Bloque")
        self.lbl_titulo.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        layout_form.addWidget(self.lbl_titulo)

        # Nombre QR
        layout_form.addWidget(QLabel("Texto del QR:"))
        self.entry_nombre = QLineEdit()
        self.entry_nombre.setPlaceholderText("ej: encender leds")
        layout_form.addWidget(self.entry_nombre)

        # Código Python
        layout_form.addWidget(QLabel("Código Python:"))
        self.entry_codigo = QLineEdit()
        self.entry_codigo.setPlaceholderText("ej: display.show")
        layout_form.addWidget(self.entry_codigo)

        # Tipo
        layout_form.addWidget(QLabel("Tipo de Nodo:"))
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems(["funcion", "valor", "control", "sujeto", "metodo", "operador_logico"])
        layout_form.addWidget(self.cb_tipo)

        # Argumentos
        layout_form.addWidget(QLabel("Argumentos:"))
        self.entry_args = QLineEdit("0")
        layout_form.addWidget(self.entry_args)

        # Botones
        layout_botones = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar Bloque")
        self.btn_guardar.setStyleSheet("background-color: #2FA572; color: white; padding: 8px;")
        self.btn_guardar.clicked.connect(self.accion_guardar)
        layout_botones.addWidget(self.btn_guardar)
        
        self.btn_cancelar = QPushButton("Cancelar Edición")
        self.btn_cancelar.setStyleSheet("background-color: #E74C3C; color: white; padding: 8px;")
        self.btn_cancelar.clicked.connect(self._reset_formulario)
        self.btn_cancelar.hide() 
        layout_botones.addWidget(self.btn_cancelar)
        
        layout_form.addLayout(layout_botones)

        self.lbl_estado = QLabel("")
        layout_form.addWidget(self.lbl_estado)

        layout_principal.addWidget(panel_form, stretch=1)

        # ==========================================
        # PANEL DERECHO: LISTA DE ELEMENTOS
        # ==========================================
        panel_lista = QFrame()
        layout_lista = QVBoxLayout(panel_lista)
        
        lbl_lista = QLabel("Bloques Actuales en Memoria")
        lbl_lista.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout_lista.addWidget(lbl_lista)

        # --- NUEVO: BARRA DE BÚSQUEDA Y BOTÓN DE BORRADO MASIVO ---
        layout_buscador = QHBoxLayout()
        layout_buscador.addWidget(QLabel("🔍 Buscar:"))
        self.buscador = BuscadorAutoLimpiable()
        self.buscador.setPlaceholderText("Escribe para filtrar bloques...")
        self.buscador.textChanged.connect(self._filtrar_tabla)
        layout_buscador.addWidget(self.buscador)
        
        self.btn_borrar_sel = QPushButton("🗑 Borrar Seleccionados")
        self.btn_borrar_sel.setStyleSheet("background-color: #E74C3C; color: white; padding: 5px; font-weight: bold;")
        self.btn_borrar_sel.setEnabled(False) # Bloqueado por defecto
        self.btn_borrar_sel.clicked.connect(self.accion_eliminar_seleccionados)
        layout_buscador.addWidget(self.btn_borrar_sel)
        
        layout_lista.addLayout(layout_buscador)
        # --------------------------------

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4) # Añadida 1 columna para las casillas
        self.tabla.setHorizontalHeaderLabels(["Sel", "Bloque -> Traducción", "Editar", "Borrar"])
        
        # Monitorizamos los clics en las casillas
        self.tabla.itemChanged.connect(self._verificar_seleccion)
        
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Casilla
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Texto
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Editar
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Borrar
        
        layout_lista.addWidget(self.tabla)
        layout_principal.addWidget(panel_lista, stretch=2)

    def _filtrar_tabla(self, texto):
        texto = texto.lower()
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 1) # Ahora el texto está en la columna 1
            if item:
                mostrar = texto in item.text().lower()
                self.tabla.setRowHidden(fila, not mostrar)

    def _verificar_seleccion(self):
        """Bloquea o desbloquea el botón de borrado masivo según las casillas marcadas."""
        hay_seleccion = False
        for fila in range(self.tabla.rowCount()):
            item_chk = self.tabla.item(fila, 0)
            if item_chk and item_chk.checkState() == Qt.CheckState.Checked:
                hay_seleccion = True
                break
        self.btn_borrar_sel.setEnabled(hay_seleccion)

    def accion_eliminar_seleccionados(self):
        claves_a_borrar = []
        for fila in range(self.tabla.rowCount()):
            item_chk = self.tabla.item(fila, 0)
            if item_chk and item_chk.checkState() == Qt.CheckState.Checked:
                # Recuperamos la clave original que escondimos en la celda
                claves_a_borrar.append(item_chk.data(Qt.ItemDataRole.UserRole))
                
        if not claves_a_borrar: return

        exitos = 0
        for clave in claves_a_borrar:
            try:
                self.json_manager.eliminar_bloque(clave)
                if self.editando_actualmente and self.llave_original == clave:
                    self._reset_formulario()
                exitos += 1
            except Exception:
                pass

        if exitos > 0:
            self.traductor.tabla_simbolos = self.traductor._construir_tabla_simbolos()
            self._cargar_lista()
            self.lbl_estado.setText(f"Se han eliminado {exitos} bloques seleccionados.")
            self.lbl_estado.setStyleSheet("color: #E74C3C;")

    def _cargar_lista(self):
        self.tabla.blockSignals(True) # Congelamos señales para evitar falsos positivos al cargar
        self.tabla.setRowCount(0)
        bloques = self.json_manager.obtener_todos_los_bloques()
        self.tabla.setRowCount(len(bloques))

        for fila, bloque in enumerate(bloques):
            clave = bloque["clave"]
            info = bloque["info"]
            
            # Col 0: Casilla de Selección
            item_chk = QTableWidgetItem()
            item_chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_chk.setCheckState(Qt.CheckState.Unchecked)
            item_chk.setData(Qt.ItemDataRole.UserRole, clave) # Guardamos la clave pura en la memoria del item
            self.tabla.setItem(fila, 0, item_chk)

            # Col 1: Texto
            texto = f"{clave} -> {info.get('codigo', '')}"
            item = QTableWidgetItem(texto)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(fila, 1, item)

            # Col 2: Editar
            btn_edit = QPushButton("✎")
            btn_edit.setStyleSheet("background-color: #D4AC0D; color: white;")
            btn_edit.clicked.connect(lambda checked, c=clave, i=info: self._cargar_edicion(c, i))
            self.tabla.setCellWidget(fila, 2, btn_edit)

            # Col 3: Borrar
            btn_del = QPushButton("🗑")
            btn_del.setStyleSheet("background-color: #E74C3C; color: white;")
            btn_del.clicked.connect(lambda checked, c=clave: self.accion_eliminar(c))
            self.tabla.setCellWidget(fila, 3, btn_del)
            
        self.tabla.blockSignals(False)
        self._verificar_seleccion() # Actualizamos el botón tras cargar

        if self.buscador.text():
            self._filtrar_tabla(self.buscador.text())

    def _cargar_edicion(self, clave, info):
        self.editando_actualmente = True
        self.llave_original = clave
        
        self.lbl_titulo.setText(f"Editando: {clave}")
        self.btn_guardar.setText("Actualizar Bloque")
        self.btn_guardar.setStyleSheet("background-color: #8E44AD; color: white; padding: 8px;")
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
        self.btn_guardar.setStyleSheet("background-color: #2FA572; color: white; padding: 8px;")
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
            self.lbl_estado.setStyleSheet("color: #FF4C4C;")
            return

        nuevo_nodo = {"codigo": codigo, "tipo": tipo}
        if tipo in ["funcion", "metodo"]: nuevo_nodo["args"] = args
        if tipo == "sujeto": nuevo_nodo["clase"] = "general"

        nombre_antiguo = self.llave_original if self.editando_actualmente else None
        
        try:
            self.json_manager.guardar_bloque(nombre_antiguo, nombre, nuevo_nodo)
            self.traductor.tabla_simbolos = self.traductor._construir_tabla_simbolos()
            
            self.lbl_estado.setText(f"¡Bloque '{nombre}' guardado con éxito!")
            self.lbl_estado.setStyleSheet("color: #2FA572;")
            
            self._reset_formulario()
            self._cargar_lista()
        except Exception as e:
            self.lbl_estado.setText(f"Error al guardar: {e}")
            self.lbl_estado.setStyleSheet("color: #FF4C4C;")

    def accion_eliminar(self, clave):
        try:
            self.json_manager.eliminar_bloque(clave)
            self.traductor.tabla_simbolos = self.traductor._construir_tabla_simbolos()
            self._cargar_lista()
            
            if self.editando_actualmente and self.llave_original == clave:
                self._reset_formulario()
                
            self.lbl_estado.setText(f"Bloque '{clave}' eliminado.")
            self.lbl_estado.setStyleSheet("color: #E74C3C;")
        except Exception as e:
            self.lbl_estado.setText(f"Error al eliminar: {e}")
            self.lbl_estado.setStyleSheet("color: #FF4C4C;")