class JsonController:
    """Intermediario entre la pestaña de edición del diccionario y el modelo JsonManager: lee, guarda y borra bloques, refrescando la tabla de símbolos del traductor tras cada cambio"""
    """Intermediary between the dictionary-editing tab and the JsonManager model: reads, saves and deletes blocks, refreshing the translator's symbols table after each change"""

    def __init__(self, json_manager, traducer):
        """Guarda las referencias al modelo del diccionario y al traductor, cuya tabla de símbolos hay que mantener sincronizada"""
        """Stores the references to the dictionary model and the translator, whose symbols table needs to be kept in sync"""
        self.json_manager = json_manager
        self.traducer = traducer

    def get_blocks(self):
        """Lee todos los bloques del json"""
        """Reads all the blocks from the json"""
        return self.json_manager.get_all_the_blocks()

    def save_block(self, old_name, new_name, block_info):
        """Guarda un bloque modificado/creado"""
        """Saves a modified/created block"""
        self.json_manager.save_block(old_name, new_name, block_info)
        self._refresh_translator()

    def delete_block(self, clave):
        """Elimina el bloque seleccionado"""
        """Deletes the selected block"""
        self.json_manager.delete_block(clave)
        self._refresh_translator()

    def _refresh_translator(self):
        """Actualiza la tabla de simbolos del traductor tras un cambio en el diccionario"""
        """Updates the translator's symbols table after a change in the dictionary"""
        self.traducer.symbols_table = self.json_manager.build_symbols_table()