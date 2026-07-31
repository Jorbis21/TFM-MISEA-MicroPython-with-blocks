class JsonController:
    """Orquesta las acciones de la pestaña del diccionario JSON."""
    def __init__(self, json_manager, traductor):
        self.json_manager = json_manager
        self.traductor = traductor

    def obtener_bloques(self):
        return self.json_manager.obtener_todos_los_bloques()

    def guardar_bloque(self, nombre_antiguo, nombre_nuevo, info_bloque):
        self.json_manager.guardar_bloque(nombre_antiguo, nombre_nuevo, info_bloque)
        # Forzamos al traductor a recargar la tabla de símbolos en memoria
        self.traductor.tabla_simbolos = self.traductor._construir_tabla_simbolos()

    def eliminar_bloque(self, clave):
        self.json_manager.eliminar_bloque(clave)
        self.traductor.tabla_simbolos = self.traductor._construir_tabla_simbolos()