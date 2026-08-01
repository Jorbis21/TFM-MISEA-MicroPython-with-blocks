import os
import json

class JsonManager:
    """Motor encargado de gestionar las operaciones CRUD del diccionario bloques.json."""
    
    def __init__(self, config_dir):
        self.ruta_json = os.path.join(config_dir, "bloques.json")

    def obtener_todos_los_bloques(self):
        bloques = []
        if os.path.exists(self.ruta_json):
            with open(self.ruta_json, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            for clave, info in sorted(datos.items()):
                bloques.append({
                    "clave": clave,
                    "info": info
                })
        return bloques

    def guardar_bloque(self, nombre_antiguo, nombre_nuevo, info_bloque):
        try:
            with open(self.ruta_json, 'r', encoding='utf-8') as f:
                datos = json.load(f)
        except Exception:
            datos = {}
            
        if nombre_antiguo and nombre_antiguo != nombre_nuevo:
            if nombre_antiguo in datos:
                del datos[nombre_antiguo]
                
        datos[nombre_nuevo] = info_bloque
        
        with open(self.ruta_json, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)

    def eliminar_bloque(self, clave):
        try:
            with open(self.ruta_json, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                
            if clave in datos:
                del datos[clave]
                
            with open(self.ruta_json, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Fallo al eliminar en disco: {e}")

    def construir_tabla_simbolos(self):
        try:
            with open(self.ruta_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Advertencia: No se encontró {self.ruta_json}")
            return {}