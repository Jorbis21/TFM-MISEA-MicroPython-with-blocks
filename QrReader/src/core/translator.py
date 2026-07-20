import os
import json
import subprocess
import sys

class MicrobitCompiler:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.tabla_simbolos = self._construir_tabla_simbolos()
        
        # --- NUEVO: ESTADO Y MEMORIA DEL SISTEMA ---
        self.voice_manager = None
        self.memoria_variables = []  # Estructura: [{"nombre_variable": valor}]
        self.contador_var = 0        # Para el comportamiento físico por defecto

    def set_voice_manager(self, voice_manager):
        """Inyecta el motor de voz en el compilador para poder interactuar durante la traducción."""
        self.voice_manager = voice_manager

    def _construir_tabla_simbolos(self):
        ruta_json = os.path.join(self.config_dir, 'bloques.json')
        try:
            with open(ruta_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Advertencia: No se encontró {ruta_json}")
            return {}

    def _es_valor_numerico(self, token):
        try:
            float(token)
            return True
        except ValueError:
            return False

    # ========================================================
    # NUEVA LÓGICA DE VARIABLES Y MEMORIA POR VOZ
    # ========================================================
    def _aplicar_tipado(self, texto):
        """Evalúa el texto capturado para convertirlo a int, float o mantenerlo como string (con comillas)."""
        texto = texto.strip()
        try:
            val = int(texto)
            return str(val), val
        except ValueError:
            pass
        
        try:
            val = float(texto.replace(",", "."))
            return str(val), val
        except ValueError:
            pass
            
        # Si no es número, se trata como texto para Python
        return f'"{texto}"', texto

    def _gestionar_variable_voz(self, tipo_bloque):
        """Flujo Maestro de Reutilización (Contexto Rápido y Sub-bucle Profundo)."""
        from core.audio import GestorVoz
        import time

        if not self.memoria_variables:
            return self.voice_manager.bucle_confirmacion_voz("Dime el nombre de la variable")

        ultima_var = list(self.memoria_variables[-1].keys())[0]

        # 1. Petición de Contexto Rápido
        GestorVoz.leer_texto(f"¿Quieres usar la última variable declarada, llamada {ultima_var}?")
        time.sleep(3)
        resp1 = self.voice_manager.escuchar_dictado_sincrono(timeout=3)
        if resp1 and ("sí" in resp1 or "si" in resp1 or "claro" in resp1):
            return ultima_var

        # 2. Petición de Contexto Profundo
        GestorVoz.leer_texto("¿Quieres usar otra de las variables anteriores guardadas?")
        time.sleep(3)
        resp2 = self.voice_manager.escuchar_dictado_sincrono(timeout=3)
        if resp2 and ("sí" in resp2 or "si" in resp2 or "claro" in resp2):
            ultimo_texto = ""
            while True:
                GestorVoz.leer_texto("Dime el nombre de la variable para poder buscarla.")
                time.sleep(3)
                texto_busqueda = self.voice_manager.escuchar_dictado_sincrono(timeout=4)
                
                if not texto_busqueda:
                    continue
                
                ultimo_texto = texto_busqueda
                
                # Salida de rescate
                if "pasar" in texto_busqueda or "omitir" in texto_busqueda:
                    return ultimo_texto

                # Búsqueda en memoria (Ignorando mayúsculas/minúsculas)
                for var_dict in self.memoria_variables:
                    nombre_var = list(var_dict.keys())[0]
                    if texto_busqueda == nombre_var.lower():
                        return nombre_var
                
                GestorVoz.leer_texto("No he encontrado esa variable en la memoria.")
                time.sleep(2)

        # Si responde NO a todo y es una declaración nueva, entramos al flujo principal
        if tipo_bloque == "declaracion_var":
            return self.voice_manager.bucle_confirmacion_voz("Dime el nombre de la variable")
        
        # Fallback de seguridad
        return ultima_var

    def _manejar_declaracion(self, tokens):
        """Procesa el bloque [Declarar variable]."""
        if self.voice_manager and self.voice_manager.is_recording:
            # Fase A: Nombre
            nombre = self._gestionar_variable_voz("declaracion_var")
            
            # Fase B: Valor
            valor_texto = self.voice_manager.bucle_confirmacion_voz("Dime el valor de la variable")
            codigo_valor, valor_real = self._aplicar_tipado(valor_texto)
            
            # Guardado persistente
            self.memoria_variables.append({nombre: valor_real})
            
            # Limpiamos los tokens físicos de la derecha para ignorar los bloques de valor de la mesa
            tokens.clear() 
            return f"{nombre} = {codigo_valor}"
        else:
            self.contador_var += 1
            return f"var_{self.contador_var} = "

    def _manejar_asignacion(self, tokens):
        """Procesa el bloque [Valor variable]."""
        if self.voice_manager and self.voice_manager.is_recording:
            tokens.clear()
            return "" # Ignorado por el control de voz
        else:
            return f"val_{self.contador_var}"

    def _manejar_referencia(self, tokens):
        """Procesa el bloque [Variable] como sujeto o argumento."""
        if self.voice_manager and self.voice_manager.is_recording:
            nombre = self._gestionar_variable_voz("referencia_var")
            return nombre
        else:
            return f"var_{self.contador_var}"
            
    # ========================================================
    # COMPILACIÓN PRINCIPAL
    # ========================================================
    def generar_codigo(self, matriz_comandos, ruta_salida):

        self.memoria_variables = []
        self.contador_var = 0
        
        if not matriz_comandos:
            print("No se recibieron comandos para compilar.")
            return

        codigo_final = [
            "from microbit import *",
            "import speech",
            "import music",
            "import random",
            "from math import *",
            "\n# --- Sonido de inicialización ---",
            "music.pitch(587, 100)",
            "music.pitch(698, 100)",
            "music.pitch(783, 100)",
            "\n# --- Programa Principal ---"
        ]

        niveles_activos = [0] 

        for fila in matriz_comandos:
            num_tabs_fisicos = 0
            for elem in fila:
                if elem == "":
                    num_tabs_fisicos += 1
                else:
                    break
            
            tokens = [e for e in fila if e != ""]
            if not tokens:
                continue

            while len(niveles_activos) > 1 and num_tabs_fisicos < niveles_activos[-1]:
                niveles_activos.pop()
                
            if num_tabs_fisicos > niveles_activos[-1]:
                niveles_activos.append(num_tabs_fisicos)
                
            nivel_logico = len(niveles_activos) - 1
            linea_str = "    " * nivel_logico  
            
            linea_str += self.procesar_fila_tokens(tokens)
            
            codigo_final.append(linea_str)

        with open(ruta_salida, "w", encoding="utf-8") as file:
            file.write("\n".join(codigo_final) + "\n")

        print("Código compilado con éxito mediante Analizador Predictivo.")

    def procesar_fila_tokens(self, tokens):
        if not tokens: 
            return ""
        
        primer_bloque = tokens.pop(0)
        
        if self._es_valor_numerico(primer_bloque):
            info = {"codigo": str(primer_bloque), "tipo": "valor"}
        else:
            info = self.tabla_simbolos.get(primer_bloque, {})
        
        if not info:
            return f"# ERROR_SINTAXIS: Bloque '{primer_bloque}' desconocido #"
            
        tipo = info.get("tipo", "")
        codigo_base = info.get("codigo", str(primer_bloque))
        
        # Rutas dinámicas para la gestión de variables
        if tipo == "declaracion_var":
            return self._manejar_declaracion(tokens)
        elif tipo == "asignacion_val":
            return self._manejar_asignacion(tokens)
        elif tipo == "referencia_var":
            return self._manejar_referencia(tokens)

        # Rutas estándar del autómata...
        if tipo == "control_metodo":
            if not tokens: return f"# ERROR: '{primer_bloque}' necesita un sujeto a su derecha"
            sujeto = self._consumir_argumento_vc(tokens)
            if codigo_base.endswith(")"): return f"if {sujeto}{codigo_base}:"
            else: return f"if {sujeto}{codigo_base}():"

        elif tipo == "control_funcion":
            if not tokens: return f"# ERROR: '{primer_bloque}' necesita un argumento a su derecha"
            arg = self._consumir_argumento_vc(tokens)
            return f"if {codigo_base}({arg}):"

        elif tipo == "metodo":
            if not tokens: return f"# ERROR: '{primer_bloque}' necesita un sujeto a su derecha"
            sujeto = self._consumir_argumento_vc(tokens)
            num_args = info.get("args", 0)
            args_extra = []
            for _ in range(num_args):
                if tokens:
                    args_extra.append(self._consumir_argumento_vc(tokens))
                    
            if args_extra: return f"{sujeto}{codigo_base}({', '.join(args_extra)})"
            else:
                if codigo_base.endswith(")"): return f"{sujeto}{codigo_base}"
                return f"{sujeto}{codigo_base}()"
                
        elif tipo == "funcion":
            num_args = info.get("args", 1)
            if num_args == 0:
                if codigo_base.endswith(")"): return codigo_base
                return f"{codigo_base}()"
                
            args = []
            for _ in range(num_args):
                if tokens:
                    args.append(self._consumir_argumento_vc(tokens))
            return f"{codigo_base}({', '.join(args)})"
            
        elif tipo == "control":
            condicion = ""
            if tokens:
                condicion = self._consumir_argumento_vc(tokens)
            codigo_limpio = codigo_base.replace(":", "").strip()
            if condicion: return f"{codigo_limpio} {condicion}:"
            else: return f"{codigo_limpio}:"
                
        else:
            tokens.insert(0, primer_bloque)
            return self._consumir_argumento_vc(tokens)

    def _consumir_argumento_vc(self, tokens):
        if not tokens: return ""
        
        val = tokens.pop(0)
        
        if self._es_valor_numerico(val):
            resultado = str(val)
        else:
            info = self.tabla_simbolos.get(val, {})
            tipo_val = info.get("tipo", "")
            
            # Inyección de lectura de variables incrustadas como argumentos
            if tipo_val == "referencia_var":
                resultado = self._manejar_referencia(tokens)
            elif tipo_val == "asignacion_val":
                resultado = self._manejar_asignacion(tokens)
            else:
                resultado = info.get("codigo", val)
            
        while tokens:
            if self._es_valor_numerico(tokens[0]):
                break
                
            sig_info = self.tabla_simbolos.get(tokens[0], {})
            tipo_sig = sig_info.get("tipo")
            
            if tipo_sig == "operador_logico":
                op = tokens.pop(0)
                resultado += sig_info.get("codigo", op)
                if tokens:
                    resultado += self._consumir_argumento_vc(tokens)
                break
                
            elif tipo_sig == "metodo":
                metodo = tokens.pop(0)
                codigo_metodo = sig_info.get("codigo", metodo)
                
                num_args = sig_info.get("args", 0)
                args_extra = []
                for _ in range(num_args):
                    if tokens:
                        args_extra.append(self._consumir_argumento_vc(tokens))
                        
                if args_extra:
                    resultado += f"{codigo_metodo}({', '.join(args_extra)})"
                else:
                    if codigo_metodo.endswith(")"):
                        resultado += codigo_metodo
                    else:
                        resultado += f"{codigo_metodo}()"
            else:
                break
                
        return resultado

    def subir(self, ruta_codigo):
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {ruta_codigo}")
        try:
            subprocess.run([sys.executable, "-m", "uflash", ruta_codigo], check=True)
            print("¡Código subido con éxito a la micro:bit!")
        except subprocess.CalledProcessError as e:
            print(f"Error al intentar comunicarse con uflash: {e}")
        except FileNotFoundError:
            print("Error: No se encuentra Python o uflash en el sistema.")