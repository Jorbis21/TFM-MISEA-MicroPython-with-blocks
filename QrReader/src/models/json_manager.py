import os, json

class JsonManager:
    
    def __init__(self, config_dir):
        self.json_dir = os.path.join(config_dir, "blocks.json")

    def get_all_the_blocks(self):
        """Obtiene todos los bloques del json"""
        """Gets all the blocks from the json"""
        blocks = []
        if os.path.exists(self.json_dir):
            with open(self.json_dir, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
            with open(self.json_dir, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
            
        if old_name and old_name != new_name:
            if old_name in data:
                del data[old_name]
                
        data[new_name] = block_info
        
        with open(self.json_dir, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def delete_block(self, key):
        """Borra el bloque seleccionado"""
        """Deletes the selected block"""
        try:
            with open(self.json_dir, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if key in data:
                del data[key]
                
            with open(self.json_dir, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Fallo al eliminar en disco: {e}")

    def build_symbols_table(self):
        """Lee todo el json"""
        """Reads all the json"""
        try:
            with open(self.json_dir, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Advertencia: No se encontró {self.json_dir}")
            return {}