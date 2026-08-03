
'''Esta clase o el manager necesita un observer para modificar el traductor'''

class JsonController:
    def __init__(self, json_manager, traductor):
        self.json_manager = json_manager
        self.traductor = traductor

    '''Lee todos los bloques del json'''
    def obtener_bloques(self):
        return self.json_manager.obtener_todos_los_bloques()

    '''Guarda un bloque modificado'''
    def guardar_bloque(self, nombre_antiguo, nombre_nuevo, info_bloque):
        self.json_manager.guardar_bloque(nombre_antiguo, nombre_nuevo, info_bloque)
        self.traductor.tabla_simbolos = self.json_manager.construir_tabla_simbolos()

    '''Elimina el bloque seleccionado'''
    def eliminar_bloque(self, clave):
        self.json_manager.eliminar_bloque(clave)
        self.traductor.tabla_simbolos = self.json_manager.construir_tabla_simbolos()

