import threading
from utils.constants import ModoTTS
from utils.matrix_process import fusionar_matrices_espaciales

class CameraController:
    def __init__(self, traductor, gestor_archivos, audio_service, ruta_codigo):
        self.traductor = traductor
        self.gestor_archivos = gestor_archivos
        self.ruta_codigo = ruta_codigo
        self.audio_service = audio_service
        self.voice_manager = None
        
        self.super_matriz = []
        self.cola_ampliaciones = []
        self.nexos_pendientes = []
        self.direccion_actual = "desconocida"
        self.estoy_ampliando = False

    def set_voice_manager(self, voice_manager):
        self.voice_manager = voice_manager

    def cargar_estado(self):
        self.super_matriz, historial = self.gestor_archivos.cargar_estado()
        self.traductor.historial_interacciones = historial

    def guardar_estado(self):
        historial = self.traductor.historial_interacciones
        self.gestor_archivos.guardar_estado(self.super_matriz, historial)

    def procesar_captura(self, matriz_espacial, desbordamiento, callback_actualizacion_ui):
        if self.estoy_ampliando:
            self.super_matriz = fusionar_matrices_espaciales(
                self.super_matriz, 
                matriz_espacial, 
                self.nexos_pendientes, 
                self.direccion_actual
            )
        else:
            self.super_matriz = matriz_espacial
            self.cola_ampliaciones = []
            
        if desbordamiento:
            if desbordamiento.get("derecha"):
                self.cola_ampliaciones.append(("lateral", desbordamiento["derecha"]))
            if desbordamiento.get("abajo"):
                self.cola_ampliaciones.append(("inferior", [desbordamiento["abajo"]]))

        self._procesar_siguiente_ampliacion(callback_actualizacion_ui)

    def _procesar_siguiente_ampliacion(self, callback_actualizacion_ui):
        if not self.cola_ampliaciones:
            self.estoy_ampliando = False
            
            # Compila del tirón, el traductor ya se encargará del micrófono
            self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, modo_repaso=False) 
            
            self.guardar_estado()
            callback_actualizacion_ui()
            return

        direccion, nexos = self.cola_ampliaciones.pop(0)
        self.direccion_actual = direccion
        self.nexos_pendientes = nexos

        nombres_pronunciar = []
        for n in nexos:
            pronunciacion = self.traductor.tabla_simbolos.get(n.lower(), {}).get("pronunciacion", n)
            if pronunciacion not in nombres_pronunciar:
                nombres_pronunciar.append(pronunciacion)
                
        nombres_str = ", y ".join(nombres_pronunciar)

        if self.voice_manager is not None:
            respuesta = self.voice_manager.bucle_confirmacion_voz(
                f"El bloque {nombres_str} toca el borde {direccion}. ¿Quieres ampliar el programa haciendo otra foto?",
                es_pregunta_abierta=False
            )
            
            if "sí" in respuesta or "si" in respuesta:
                self.estoy_ampliando = True
                self.audio_service.leer_texto(f"De acuerdo. Pon el bloque {nombres_str} en la nueva foto para usarlo de referencia. Pulsa capturar cuando estés listo.")
                return 
            else:
                self.audio_service.leer_texto("De acuerdo, cancelando el resto de ampliaciones y procesando el programa.")
                self.cola_ampliaciones.clear()
                
        self.estoy_ampliando = False
        self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, modo_repaso=False) 
        
        self.guardar_estado()
        callback_actualizacion_ui()

    def repasar_variables(self, callback_actualizacion_ui):
        if not self.super_matriz:
            self.audio_service.leer_texto_interrumpiendo("Primero debes capturar un programa para poder modificar sus variables.")
            return
            
        self.audio_service.leer_texto_interrumpiendo("Iniciando el modo de repaso de variables.")

        self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, modo_repaso=True)
        
        self.guardar_estado()
        callback_actualizacion_ui()

    def obtener_codigo_vista(self):
        try:
            with open(self.ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
        except FileNotFoundError:
            return "# Archivo no generado de momento.", "Estado: Esperando captura...", [], False

        lineas = codigo.split('\n')
        linea_corte_fin = -1
        linea_corte_ini = -1
        for i, linea in enumerate(lineas):
            if "# --- Sonido de inicialización ---" in linea:
                linea_corte_ini = i
            if "# --- Programa Principal ---" in linea: 
                linea_corte_fin = i
                break

        bloque_pitches = []
        if linea_corte_ini != -1 and linea_corte_fin != -1:
            lineas_visibles = []
            for i, linea in enumerate(lineas):
                if i < linea_corte_ini:
                    lineas_visibles.append(linea)
                elif i >= linea_corte_ini and i <= linea_corte_fin:
                    bloque_pitches.append(linea)
                else:
                    lineas_visibles.append(linea)

            codigo_mostrar = "\n".join(lineas_visibles)
        else:
            codigo_mostrar = codigo

        estado = "Estado: Código sin errores"
        hay_error = False
        
        codigo_a_compilar = codigo_mostrar.replace('\xa0', ' ').replace('\t', '    ') + '\n'

        try:
            compile(codigo_a_compilar, '<string>', 'exec')
        except SyntaxError as e:
            estado = f"Error de Sintaxis en línea {e.lineno}"
            hay_error = True

        return codigo_mostrar, estado, bloque_pitches, hay_error

    def procesar_qrs_pantalla(self, frame_bgr, vision, workspace_dir):
        import os
        if frame_bgr is None:
            self.audio_service.leer_texto("La cámara no está activa.")
            return
            
        ruta_temp = os.path.join(workspace_dir, "outputs", "temp_leer.jpg")
        vision.takePhoto(frame_bgr, ruta_temp)
        matriz_ordenada = vision.get_command_matrix()
        
        textos_a_leer = []
        for fila in matriz_ordenada:
            for bloque in fila:
                if bloque.strip() != "":
                    clave_busqueda = str(bloque).strip().lower()
                    info_bloque = self.traductor.tabla_simbolos.get(clave_busqueda, {})
                    pronunciacion = info_bloque.get("pronunciacion", str(bloque))
                    textos_a_leer.append(pronunciacion)
                    
        if textos_a_leer:
            self.audio_service.leer_qrs_pantalla(textos_a_leer)
        else:
            self.audio_service.leer_texto("No detecto ningún bloque en la pantalla.")

    def guardar_codigo_manual(self, nuevo_codigo, bloque_pitches):
        codigo_limpio = nuevo_codigo.replace('\xa0', ' ').replace('\t', '    ')
        return self.gestor_archivos.guardar_codigo_editado(codigo_limpio, bloque_pitches)

    def enviar_a_microbit(self):
        self.audio_service.leer_texto("Subiendo el programa a la placa Micro:bit.")
        self.gestor_archivos.subir()    

    def explicar_codigo_ia(self, ai_manager, callback_estado):
        threading.Thread(target=lambda: ai_manager.explicar_codigo(self.ruta_codigo, callback_estado), daemon=True).start()

    def alternar_tts(self, modos_tts, idx_actual):
        siguiente_idx = (idx_actual + 1) % len(modos_tts)
        modo = modos_tts[siguiente_idx]
        
        if self.traductor is not None:
            self.traductor.set_modo_tts(modo["valor"])
            
        if modo["valor"] == ModoTTS.PC.value:
            self.audio_service.leer_texto("Modo de voz por ordenador activado.")
        elif modo["valor"] == ModoTTS.PLACA.value:
            self.audio_service.leer_texto("Modo de voz en la placa activado.")
        elif modo["valor"] == ModoTTS.APAGADO.value:
            self.audio_service.leer_texto("Voz de ejecución desactivada.")
            
        return siguiente_idx, modo["texto"]