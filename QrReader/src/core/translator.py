import os
import json
import subprocess
import sys

class MicrobitCompiler:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.tabla_simbolos = self._construir_tabla_simbolos()

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
        
    def generar_codigo(self, matriz_comandos, ruta_salida):
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

        # NUEVO: Pila para mapear huecos físicos a niveles lógicos de Python
        niveles_activos = [0] 

        for fila in matriz_comandos:
            # 1. Análisis Léxico (Contar huecos físicos de la cámara)
            num_tabs_fisicos = 0
            for elem in fila:
                if elem == "":
                    num_tabs_fisicos += 1
                else:
                    break
            
            tokens = [e for e in fila if e != ""]
            if not tokens:
                continue

            # 2. Normalización de Indentación (A prueba de cámaras y muescas 3D)
            # Si volvemos hacia la izquierda, sacamos niveles de la pila
            while len(niveles_activos) > 1 and num_tabs_fisicos < niveles_activos[-1]:
                niveles_activos.pop()
                
            # Si vamos hacia la derecha, añadimos un nuevo nivel
            if num_tabs_fisicos > niveles_activos[-1]:
                niveles_activos.append(num_tabs_fisicos)
                
            # Calculamos el nivel real y ponemos exactamente 4 espacios por nivel
            nivel_logico = len(niveles_activos) - 1
            linea_str = "    " * nivel_logico  
            
            # 3. Procesar la sintaxis
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
        
        # ========================================================
        # 1. EVENTOS ESPECIALES INVERTIDOS (Ej: al presionar)
        # ========================================================
        if tipo == "control_metodo":
            if not tokens:
                return f"# ERROR: '{primer_bloque}' necesita un sujeto a su derecha"
            
            sujeto = self._consumir_argumento_vc(tokens)
            if codigo_base.endswith(")"):
                return f"if {sujeto}{codigo_base}:"
            else:
                return f"if {sujeto}{codigo_base}():"

        # ========================================================
        # 2. EVENTOS ESPECIALES DE FUNCIÓN (Ej: al gesto)
        # ========================================================
        elif tipo == "control_funcion":
            if not tokens:
                return f"# ERROR: '{primer_bloque}' necesita un argumento a su derecha"
            
            arg = self._consumir_argumento_vc(tokens)
            return f"if {codigo_base}({arg}):"

        # ========================================================
        # 3. ES UN MÉTODO NORMAL (INVERSIÓN OBLIGATORIA POR HARDWARE)
        # ========================================================
        elif tipo == "metodo":
            if not tokens:
                return f"# ERROR: '{primer_bloque}' necesita un sujeto a su derecha"
            
            sujeto = self._consumir_argumento_vc(tokens)
            num_args = info.get("args", 0)
            args_extra = []
            for _ in range(num_args):
                if tokens:
                    args_extra.append(self._consumir_argumento_vc(tokens))
                    
            if args_extra:
                return f"{sujeto}{codigo_base}({', '.join(args_extra)})"
            else:
                if codigo_base.endswith(")"):
                    return f"{sujeto}{codigo_base}"
                return f"{sujeto}{codigo_base}()"
                
        # ========================================================
        # 4. ES UNA FUNCIÓN NORMAL
        # ========================================================
        elif tipo == "funcion":
            num_args = info.get("args", 1)
            
            if num_args == 0:
                if codigo_base.endswith(")"):
                    return codigo_base
                return f"{codigo_base}()"
                
            args = []
            for _ in range(num_args):
                if tokens:
                    args.append(self._consumir_argumento_vc(tokens))
            return f"{codigo_base}({', '.join(args)})"
            
        # ========================================================
        # 5. ES UN BLOQUE DE CONTROL CLÁSICO (si, mientras)
        # ========================================================
        elif tipo == "control":
            condicion = ""
            if tokens:
                condicion = self._consumir_argumento_vc(tokens)
                
            codigo_limpio = codigo_base.replace(":", "").strip()
            if condicion:
                return f"{codigo_limpio} {condicion}:"
            else:
                return f"{codigo_limpio}:"
                
        # ========================================================
        # 6. CASO BASE O CADENA DE VARIABLES PURA
        # ========================================================
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