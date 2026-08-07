import threading, re, os
from utils.constants import TTSMode, EventType
from controllers.camera_worker import CameraWorker

class CameraController:
    
    def __init__(self, traductor, gestor_archivos, audio_service, ruta_codigo, vision_engine, ai_manager, workspace_dir, voice_manager):
        self.traductor = traductor
        self.gestor_archivos = gestor_archivos
        self.ruta_codigo = ruta_codigo
        self.audio_service = audio_service
        self.vision = vision_engine
        self.ai_manager = ai_manager
        self.workspace_dir = workspace_dir
        self.voice_manager = voice_manager

        self.hilo_camara = CameraWorker(self.vision)

        self.super_matriz, self.traductor.historial_interacciones = self.gestor_archivos.cargar_estado()
        self.cola_ampliaciones = []
        self.nexos_pendientes = []
        self.direccion_actual = "desconocida"
        self.estoy_ampliando = False

    def guardar_estado(self):
        """Guarda el estado del programa y las interacciones hechas"""
        self.gestor_archivos.guardar_estado(self.super_matriz, self.traductor.historial_interacciones)
        
    def repasar_variables(self, callback_actualizacion_ui):
        if not self.super_matriz:
            self.audio_service.leer_texto_interrumpiendo("Primero debes capturar un programa para poder modificar sus variables.")
            return
            
        self.audio_service.leer_texto_interrumpiendo("Iniciando el modo de repaso de variables.")
        necesidades = self.traductor.analizar_matriz(self.super_matriz)
        respuestas = self._ejecutar_interaccion_variables(necesidades, modo_repaso=True)
        self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, respuestas)
        self.guardar_estado()
        self.audio_service.leer_texto("Variables modificadas. El código nuevo ya está generado.")
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
            if "# --- Sonido de inicialización ---" in linea: linea_corte_ini = i
            if "# --- Programa Principal ---" in linea: 
                linea_corte_fin = i
                break

        bloque_pitches = []
        if linea_corte_ini != -1 and linea_corte_fin != -1:
            lineas_visibles = []
            for i, linea in enumerate(lineas):
                if i < linea_corte_ini: lineas_visibles.append(linea)
                elif i >= linea_corte_ini and i <= linea_corte_fin: bloque_pitches.append(linea)
                else: lineas_visibles.append(linea)
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

    def procesar_qrs_pantalla(self, frame_bgr):
        """Absorbe la lógica de visión desde la Vista."""
        if frame_bgr is None:
            self.audio_service.leer_texto("La cámara no está activa.")
            return
            
        ruta_temp = os.path.join(self.workspace_dir, "outputs", "temp_leer.jpg")
        self.vision.takePhoto(frame_bgr, ruta_temp)
        matriz_ordenada = self.vision.get_command_matrix()
        
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
        exito, msg = self.gestor_archivos.subir() 
        if not exito:
            self.audio_service.leer_texto_interrumpiendo(msg)

    def explicar_codigo_ia(self, callback_estado):
        """No necesita recibir AI_Manager, ya lo tiene."""
        threading.Thread(target=lambda: self.ai_manager.explicar_codigo(self.ruta_codigo, callback_estado), daemon=True).start()

    def alternar_tts(self, modos_tts, idx_actual):
        siguiente_idx = (idx_actual + 1) % len(modos_tts)
        modo = modos_tts[siguiente_idx]
        
        if self.traductor is not None:
            self.traductor.set_modo_tts(modo["valor"])
            
        if modo["valor"] == TTSMode.PC.value:
            self.audio_service.leer_texto("Modo de voz por ordenador activado.")
        elif modo["valor"] == TTSMode.BOARD.value:
            self.audio_service.leer_texto("Modo de voz en la placa activado.")
        elif modo["valor"] == TTSMode.SHUTDONW.value:
            self.audio_service.leer_texto("Voz de ejecución desactivada.")
            
        return siguiente_idx, modo["texto"]

    def iniciar_camara_hardware(self, idx, rotar=False):
        self.hilo_camara.rotar = rotar
        self.hilo_camara.iniciar_hardware(idx)

    def pausar_camara_hardware(self):
        self.hilo_camara.pausar_hardware()

    def set_rotacion_camara(self, rotar):
        self.hilo_camara.rotar = rotar
        if rotar:
            self.audio_service.leer_texto_interrumpiendo("Cámara en modo vertical.")
        else:
            self.audio_service.leer_texto_interrumpiendo("Cámara en modo horizontal.")

    def liberar_recursos_camara(self):
        self.hilo_camara.liberar_todo()

 # --- LÓGICA DE INTERACCIÓN DE VOZ ---
    def _ejecutar_interaccion_variables(self, necesidades, modo_repaso):
        respuestas = []
        memoria_simulada = []
        historial = self.traductor.historial_interacciones if modo_repaso else []
        indice_repaso = 0
        
        for nec in necesidades:
            tipo = nec["tipo"]
            contexto = nec["contexto"]
            
            if "var_" in contexto and memoria_simulada:
                contexto = re.sub(r'var_\d+', memoria_simulada[-1], contexto)
            
            respuesta_cruda = self._interactuar_voz(tipo, contexto, memoria_simulada, modo_repaso, historial, indice_repaso)
            
            es_var = (tipo != "asignacion_val")
            res_limpia = self.traductor._normalizar_texto(respuesta_cruda, es_variable=es_var)
            
            if not modo_repaso:
                historial.append(res_limpia)
            else:
                if indice_repaso < len(historial):
                    historial[indice_repaso] = res_limpia
                indice_repaso += 1
                
            respuestas.append(res_limpia)
            
            if tipo == "declaracion_var":
                memoria_simulada.append(res_limpia)
                
        if not modo_repaso:
            self.traductor.historial_interacciones = historial
        return respuestas

    def _interactuar_voz(self, tipo_bloque, contexto, memoria_variables, modo_repaso, historial, indice_repaso):
        intro = f"Para {contexto}. " if contexto else ""
        if not self.voice_manager: return "0" if tipo_bloque == "asignacion_val" else "var"
        
        if modo_repaso and indice_repaso < len(historial):
            valor_anterior = historial[indice_repaso]
            if tipo_bloque == "asignacion_val":
                self.audio_service.leer_texto(f"{intro}El valor actual es {valor_anterior}. ¿Quieres modificarlo?")
            else:
                self.audio_service.leer_texto(f"{intro}El nombre actual es {valor_anterior}. ¿Quieres modificarlo?")
                
            evento = self.voice_manager.escuchar_dictado_sincrono()
            quiere_modificar = (
                (evento.tipo == EventType.TAP and evento.es_afirmativo) or 
                (evento.tipo == EventType.VOICE and ("sí" in evento.texto or "si" in evento.texto))
            )
            
            if quiere_modificar:
                pregunta = "Dime el nuevo valor" if tipo_bloque == "asignacion_val" else "Dime el nuevo nombre"
                return self.voice_manager.bucle_confirmacion_voz(pregunta, "0" if tipo_bloque == "asignacion_val" else "var")
            return valor_anterior

        if tipo_bloque == "asignacion_val": return self.voice_manager.bucle_confirmacion_voz(f"{intro}Dime el valor", "0")
        if tipo_bloque == "declaracion_var": return self.voice_manager.bucle_confirmacion_voz(f"{intro}Dime el nombre de la variable", "var")
        if not memoria_variables: return self.voice_manager.bucle_confirmacion_voz(f"{intro}Dime el nombre de la variable", "var")
            
        ultima_var = memoria_variables[-1]
        self.audio_service.leer_texto(f"{intro}¿Quieres usar la última variable declarada, llamada {ultima_var}?")
        resp1 = self.voice_manager.escuchar_dictado_sincrono()
        usar_ultima = (
            (resp1.tipo == EventType.TAP and resp1.es_afirmativo) or 
            (resp1.tipo == EventType.VOICE and any(p in resp1.texto for p in ["sí", "si", "claro", "correcto"]))
        )
        if usar_ultima: return ultima_var

        if len(memoria_variables) > 1:
            self.audio_service.leer_texto("¿Quieres usar otra de las variables anteriores?")
            resp2 = self.voice_manager.escuchar_dictado_sincrono()
            usar_otra = (
                (resp2.tipo == EventType.TAP and resp2.es_afirmativo) or 
                (resp2.tipo == EventType.VOICE and any(p in resp2.texto for p in ["sí", "si", "claro", "correcto"]))
            )
            if usar_otra:
                while True:
                    self.audio_service.leer_texto("Dime el nombre de la variable para buscarla.")
                    busqueda = self.voice_manager.escuchar_dictado_sincrono()
                    if busqueda.tipo == EventType.TAP:
                        self.audio_service.leer_texto("Por favor, dime el nombre hablando.")
                        continue
                    texto_busqueda = self.traductor._normalizar_texto(busqueda.texto, es_variable=True)
                    if "pasar" in texto_busqueda or "omitir" in texto_busqueda: return "var"
                    if texto_busqueda in memoria_variables: return texto_busqueda
                    self.audio_service.leer_texto("No he encontrado esa variable. Volvamos a intentarlo.")

        return self.voice_manager.bucle_confirmacion_voz(f"{intro}Dime el nombre", "var")

    # --- FLUJO PRINCIPAL DE CÁMARA (MVC PURO) ---

    def _fusionar_matrices_espaciales(matriz_base, matriz_nueva, nexos_esperados, direccion="desconocida"):
        """
        Toma dos matrices de bloques detectados por visión artificial y las fusiona 
        basándose en los nexos y la dirección de desbordamiento.
        """
        genericos = ["valor_variable", "numero", "texto", "verdadero", "falso", "imagen"]
        nexos_fuertes = [n for n in nexos_esperados if str(n).strip().lower() not in genericos]
        anclajes = nexos_fuertes if nexos_fuertes else nexos_esperados
        
        nueva_super_matriz = [fila.copy() for fila in matriz_base]
        
        if direccion == "lateral":
            filas_mapeadas_en_nueva = set()
            offset_c_global = 0 
            
            for nexo in anclajes:
                nexo_str = str(nexo).strip().lower()
                r_base, c_base, r_nueva, c_nueva = -1, -1, -1, -1
                
                for r in range(len(nueva_super_matriz)):
                    for c in range(len(nueva_super_matriz[r])):
                        if str(nueva_super_matriz[r][c]).strip().lower() == nexo_str:
                            r_base, c_base = r, c
                            break
                    if r_base != -1: break
                
                for r in range(len(matriz_nueva)):
                    for c in range(len(matriz_nueva[r])):
                        if str(matriz_nueva[r][c]).strip().lower() == nexo_str:
                            r_nueva, c_nueva = r, c
                            break
                    if r_nueva != -1: break
                
                if r_base != -1 and r_nueva != -1:
                    filas_mapeadas_en_nueva.add(r_nueva)
                    offset_c_global = c_base - c_nueva
                    
                    for c in range(c_nueva + 1, len(matriz_nueva[r_nueva])):
                        val = matriz_nueva[r_nueva][c]
                        target_c = c + offset_c_global
                        while len(nueva_super_matriz[r_base]) <= target_c:
                            nueva_super_matriz[r_base].append("")
                        if val != "":
                            nueva_super_matriz[r_base][target_c] = val
                            
            if filas_mapeadas_en_nueva:
                max_r_mapeada = max(filas_mapeadas_en_nueva)
                for r in range(max_r_mapeada + 1, len(matriz_nueva)):
                    nueva_fila = []
                    for c in range(len(matriz_nueva[r])):
                        val = matriz_nueva[r][c]
                        target_c = c + offset_c_global
                        if target_c >= 0:
                            while len(nueva_fila) <= target_c:
                                nueva_fila.append("")
                            if val != "":
                                nueva_fila[target_c] = val
                    nueva_super_matriz.append(nueva_fila)
            else:
                for r in range(len(matriz_nueva)):
                    nueva_super_matriz.append(matriz_nueva[r])
                    
        elif direccion == "inferior":
            ancla_base_r, c_base = -1, -1
            ancla_nueva_r, c_nueva = -1, -1
            nexo_usado = None
            
            for nexo in anclajes:
                nexo_str = str(nexo).strip().lower()
                for r in range(len(nueva_super_matriz)-1, -1, -1):
                    for c in range(len(nueva_super_matriz[r])):
                        if str(nueva_super_matriz[r][c]).strip().lower() == nexo_str:
                            ancla_base_r, c_base = r, c
                            break
                    if ancla_base_r != -1: break
                
                for r in range(len(matriz_nueva)):
                    for c in range(len(matriz_nueva[r])):
                        if str(matriz_nueva[r][c]).strip().lower() == nexo_str:
                            ancla_nueva_r, c_nueva = r, c
                            break
                    if ancla_nueva_r != -1: break
                
                if ancla_base_r != -1 and ancla_nueva_r != -1:
                    nexo_usado = nexo
                    break
            
            if nexo_usado:
                offset_c = c_base - c_nueva
                
                for c in range(c_nueva + 1, len(matriz_nueva[ancla_nueva_r])):
                    val = matriz_nueva[ancla_nueva_r][c]
                    target_c = c + offset_c
                    while len(nueva_super_matriz[ancla_base_r]) <= target_c:
                        nueva_super_matriz[ancla_base_r].append("")
                    if val != "":
                        nueva_super_matriz[ancla_base_r][target_c] = val
                
                for r in range(ancla_nueva_r + 1, len(matriz_nueva)):
                    nueva_fila = []
                    for c in range(len(matriz_nueva[r])):
                        val = matriz_nueva[r][c]
                        target_c = c + offset_c
                        if target_c >= 0:
                            while len(nueva_fila) <= target_c:
                                nueva_fila.append("")
                            if val != "":
                                nueva_fila[target_c] = val
                    nueva_super_matriz.append(nueva_fila)
            else:
                for r in range(len(matriz_nueva)):
                    nueva_super_matriz.append(matriz_nueva[r])
        else:
            for r in range(len(matriz_nueva)):
                nueva_super_matriz.append(matriz_nueva[r])
                
        return nueva_super_matriz
    def procesar_captura_completa(self, frame_bgr, ruta_img, callback_actualizacion_ui):
        """Absorbe la lógica que antes estaba en la Vista."""
        self.audio_service.leer_texto("Capturando.")
        self.vision.takePhoto(frame_bgr, ruta_img)
        matriz_espacial = self.vision.get_command_matrix()
        desbordamiento = self.vision.comprobar_desbordamiento()
        
        # Flujo antiguo de procesar_captura
        if self.estoy_ampliando:
            self.super_matriz = self._fusionar_matrices_espaciales(
                self.super_matriz, matriz_espacial, self.nexos_pendientes, self.direccion_actual
            )
        else:
            self.super_matriz = matriz_espacial
            self.cola_ampliaciones = []
            
        if desbordamiento:
            if desbordamiento.get("derecha"): self.cola_ampliaciones.append(("lateral", desbordamiento["derecha"]))
            if desbordamiento.get("abajo"): self.cola_ampliaciones.append(("inferior", [desbordamiento["abajo"]]))

        self._procesar_siguiente_ampliacion(callback_actualizacion_ui)

    def _procesar_siguiente_ampliacion(self, callback_actualizacion_ui):
        if not self.cola_ampliaciones:
            self.estoy_ampliando = False
            necesidades = self.traductor.analizar_matriz(self.super_matriz)
            respuestas = self._ejecutar_interaccion_variables(necesidades, modo_repaso=False)
            self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, respuestas) 
            self.guardar_estado()
            self.audio_service.leer_texto("El código nuevo ya está generado.")
            callback_actualizacion_ui()
            return

        direccion, nexos = self.cola_ampliaciones.pop(0)
        self.direccion_actual = direccion
        self.nexos_pendientes = nexos

        nombres_pronunciar = []
        for n in nexos:
            pronunciacion = self.traductor.tabla_simbolos.get(n.lower(), {}).get("pronunciacion", n)
            if pronunciacion not in nombres_pronunciar: nombres_pronunciar.append(pronunciacion)
                
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
        necesidades = self.traductor.analizar_matriz(self.super_matriz)
        respuestas = self._ejecutar_interaccion_variables(necesidades, modo_repaso=False)
        self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, respuestas) 
        self.guardar_estado()
        self.audio_service.leer_texto("El código nuevo ya está generado.")
        callback_actualizacion_ui()