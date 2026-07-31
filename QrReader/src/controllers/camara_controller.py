# core/controlador_sesion.py

import threading
from utils.constants import ModoTTS
from PyQt6.QtCore import QTimer
from models.audio import GestorVoz
from utils.matrix_process import fusionar_matrices_espaciales

class CamaraController:
    def __init__(self, traductor, gestor_archivos, ruta_codigo):
        self.traductor = traductor
        self.gestor_archivos = gestor_archivos
        self.ruta_codigo = ruta_codigo
        
        # Estado de la sesión (El Modelo de datos)
        self.super_matriz = []
        self.cola_ampliaciones = []
        self.nexos_pendientes = []
        self.direccion_actual = "desconocida"
        self.estoy_ampliando = False

    def cargar_estado(self):
        """Carga el estado al abrir la aplicación."""
        self.super_matriz, historial = self.gestor_archivos.cargar_estado()
        if self.traductor is not None:
            self.traductor.historial_interacciones = historial

    def guardar_estado(self):
        """Guarda el estado actual en el disco."""
        historial = self.traductor.historial_interacciones if self.traductor is not None else []
        self.gestor_archivos.guardar_estado(self.super_matriz, historial)

    def procesar_captura(self, matriz_espacial, desbordamiento, callback_actualizacion_ui):
        """Lógica central: fusiona matrices y evalúa si hay que ampliar."""
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
        """Lógica del bucle de voz para hacer expansiones de código."""
        if not self.cola_ampliaciones:
            self.estoy_ampliando = False
            self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo) 
            self.guardar_estado()
            callback_actualizacion_ui() # Llama a leer_codigo_generado en la vista
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
        
        # Ahora se ejecuta correctamente en el hilo principal
        if self.traductor.voice_manager is not None:
            respuesta = self.traductor.voice_manager.bucle_confirmacion_voz(
                f"El bloque {nombres_str} toca el borde {direccion}. ¿Quieres ampliar el programa haciendo otra foto?",
                es_pregunta_abierta=False
            )
            
            if "sí" in respuesta or "si" in respuesta:
                self.estoy_ampliando = True
                GestorVoz.leer_texto(f"De acuerdo. Pon el bloque {nombres_str} en la nueva foto para usarlo de referencia. Pulsa capturar cuando estés listo.")
                return 
            else:
                GestorVoz.leer_texto("De acuerdo, cancelando el resto de ampliaciones y procesando el programa.")
                self.cola_ampliaciones.clear()
                
        self.estoy_ampliando = False
        self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo) 
        self.guardar_estado()
        callback_actualizacion_ui()

    def repasar_variables(self, callback_actualizacion_ui):
        """Lógica para modificar variables usando la voz."""
        if not self.super_matriz:
            GestorVoz.leer_texto_interrumpiendo("Primero debes capturar un programa para poder modificar sus variables.")
            return
            
        GestorVoz.leer_texto_interrumpiendo("Iniciando el modo de repaso de variables.")
        
        # Ahora se ejecuta correctamente en el hilo principal
        self.traductor.generar_codigo(self.super_matriz, self.ruta_codigo, modo_repaso=True)
        self.guardar_estado()
        callback_actualizacion_ui()

    def obtener_codigo_vista(self):
        """Lee el código, lo formatea para la vista y comprueba su sintaxis."""
        try:
            with open(self.ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
        except FileNotFoundError:
            return "# Archivo no generado de momento.", "Estado: Esperando captura...", [], False

        lineas = codigo.split('\n')
        idx_ultimo_pitch = -1
        for i, linea in enumerate(lineas):
            if "music.pitch" in linea: idx_ultimo_pitch = i
            if linea.startswith("while ") or linea.startswith("if ") or linea.startswith("def "): break

        bloque_pitches = []
        if idx_ultimo_pitch != -1:
            lineas_visibles = []
            for i, linea in enumerate(lineas):
                if i <= idx_ultimo_pitch:
                    if linea.startswith("import ") or linea.startswith("from "): lineas_visibles.append(linea)
                    elif "music.pitch" in linea: bloque_pitches.append(linea)
                else:
                    if i == idx_ultimo_pitch + 1 and linea.strip() == "" and lineas_visibles and lineas_visibles[-1].strip() == "": continue
                    lineas_visibles.append(linea)
            codigo_mostrar = "\n".join(lineas_visibles)
        else:
            codigo_mostrar = codigo

        estado = "Estado: Código sin errores"
        hay_error = False
        
        # --- SOLUCIÓN: Limpiamos la basura invisible del QTextEdit y aseguramos el EOF ---
        codigo_a_compilar = codigo_mostrar.replace('\xa0', ' ').replace('\t', '    ') + '\n'
        
        try:
            compile(codigo_a_compilar, '<string>', 'exec')
        except SyntaxError as e:
            estado = f"Error de Sintaxis en línea {e.lineno}"
            hay_error = True

        return codigo_mostrar, estado, bloque_pitches, hay_error

    def procesar_qrs_pantalla(self, frame_bgr, vision, workspace_dir):
        """Orquesta la lectura de QRs sueltos en pantalla."""
        import os
        if frame_bgr is None:
            GestorVoz.leer_texto("La cámara no está activa.")
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
            GestorVoz.leer_qrs_pantalla(textos_a_leer)
        else:
            GestorVoz.leer_texto("No detecto ningún bloque en la pantalla.")
            
    def guardar_codigo_manual(self, nuevo_codigo, bloque_pitches):
        # Limpiamos caracteres invisibles conflictivos antes de pasarlo al disco
        codigo_limpio = nuevo_codigo.replace('\xa0', ' ').replace('\t', '    ')
        return self.gestor_archivos.guardar_codigo_editado(codigo_limpio, bloque_pitches)

    def enviar_a_microbit(self):
        GestorVoz.leer_texto("Subiendo el programa a la placa Micro:bit.")
        self.traductor.subir(self.ruta_codigo)

    def explicar_codigo_ia(self, ai_manager, callback_estado):
        if ai_manager is not None:
            threading.Thread(target=lambda: ai_manager.explicar_codigo(self.ruta_codigo, callback_estado), daemon=True).start()

    def alternar_tts(self, modos_tts, idx_actual):
        siguiente_idx = (idx_actual + 1) % len(modos_tts)
        modo = modos_tts[siguiente_idx]
        
        if self.traductor is not None:
            self.traductor.set_modo_tts(modo["valor"])
            
        if modo["valor"] == ModoTTS.PC.value:
            GestorVoz.leer_texto("Modo de voz por ordenador activado.")
        elif modo["valor"] == ModoTTS.PLACA.value:
            GestorVoz.leer_texto("Modo de voz en la placa activado.")
        elif modo["valor"] == ModoTTS.APAGADO.value:
            GestorVoz.leer_texto("Voz de ejecución desactivada.")
            
        return siguiente_idx, modo["texto"]