import os, json
from utils.language import get_language

class JsonManager:
    """Gestiona el diccionario de bloques (lectura, guardado, borrado, y construcción de la tabla de símbolos que usa el traductor), eligiendo el archivo del idioma activo"""
    """Manages the block dictionary (reading, saving, deleting, and building the symbols table the translator uses), choosing the active language's file"""

    def __init__(self, config_dir):
        """Calcula la ruta al diccionario del idioma activo en el momento de crear el objeto (blocks_es.json o blocks_en.json)"""
        """Computes the path to the active language's dictionary at the moment this object is created (blocks_es.json or blocks_en.json)"""
        self.json_dir = os.path.join(config_dir, f"blocks_{get_language()}.json")

    def _read_data(self):
        """Lee el json del disco; si no existe, devuelve un diccionario vacio; si existe pero esta corrupto, propaga el error"""
        """Reads the json from disk; if it doesn't exist, returns an empty dict; if it exists but is corrupted, propagates the error"""
        if not os.path.exists(self.json_dir):
            return {}
        with open(self.json_dir, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_data(self, data):
        """Escribe el json en disco"""
        """Writes the json to disk"""
        with open(self.json_dir, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def get_all_the_blocks(self):
        """Obtiene todos los bloques del json"""
        """Gets all the blocks from the json"""
        try:
            data = self._read_data()
        except json.JSONDecodeError as e:
            print(f"Advertencia: El diccionario de bloques está corrupto: {e}")
            return []

        blocks = []
        for key, info in sorted(data.items()):
            blocks.append({
                "key": key,
                "info": info
            })
        return blocks

    def save_block(self, old_name, new_name, block_info):
        """Guarda el bloque modificado"""
        """Saves the modified block"""
        try:
            data = self._read_data()
        except json.JSONDecodeError as e:
            raise Exception(f"No se puede guardar: el diccionario de bloques está corrupto ({e}). Revísalo antes de seguir.")

        if old_name and old_name != new_name:
            if old_name in data:
                del data[old_name]
                
        data[new_name] = block_info
        self._write_data(data)

    def delete_block(self, key):
        """Borra el bloque seleccionado"""
        """Deletes the selected block"""
        try:
            data = self._read_data()
        except json.JSONDecodeError as e:
            raise Exception(f"No se puede eliminar: el diccionario de bloques está corrupto ({e}).")

        if key in data:
            del data[key]

        try:
            self._write_data(data)
        except Exception as e:
            raise Exception(f"Fallo al eliminar en disco: {e}")

    def build_symbols_table(self):
        """Lee todo el json"""
        """Reads all the json"""
        try:
            return self._read_data()
        except json.JSONDecodeError as e:
            print(f"Advertencia: El diccionario de bloques está corrupto: {e}")
            return {}