import os
import json
import subprocess
import sys

class MicrobitCompiler:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.tabla_simbolos = self._construir_tabla_simbolos()
        
        self.voice_manager = None
        self.memoria_variables = []  
        self.contador_var = 0        
        self.activar_voz_variables = True

    def set_voice_manager(self, voice_manager):
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
        
    def _normalizar_texto(self, texto, es_variable=False):
        if not texto: return ""
        
        texto = texto.strip().lower()
        
        reemplazos = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u'
        }
        for original, nuevo in reemplazos.items():
            texto = texto.replace(original, nuevo)
            
        if es_variable:
            texto = texto.replace(" ", "_")
            
        return texto

    def _aplicar_tipado(self, texto):
        texto = texto.strip().lower()
        
        # 1. Diccionario rápido para los números que Whisper suele escribir con letra
        numeros_letras = {
            "cero": "0", "uno": "1", "dos": "2", "tres": "3", "cuatro": "4",
            "cinco": "5", "seis": "6", "siete": "7", "ocho": "8", "nueve": "9",
            "diez": "10", "once": "11", "doce": "12", "trece": "13", "catorce": "14",
            "quince": "15", "dieciséis": "16", "diecisiete": "17", "dieciocho": "18",
            "diecinueve": "19", "veinte": "20", "treinta": "30", "cuarenta": "40",
            "cincuenta": "50", "sesenta": "60", "setenta": "70", "ochenta": "80",
            "noventa": "90", "cien": "100"
        }
        
        # Limpieza del prefijo "número " por si el usuario quiere forzarlo
        if texto.startswith("número "):
            texto = texto.replace("número ", "", 1).strip()
        elif texto.startswith("numero "):
            texto = texto.replace("numero ", "", 1).strip()
            
        # 2. Traducción automática de palabra a dígito si está en el diccionario
        if texto in numeros_letras:
            texto = numeros_letras[texto]
            
        # 3. Parseo de decimales hablados
        texto_parseado = texto.replace(" coma ", ".")
        texto_parseado = texto_parseado.replace(" con ", ".")
        texto_parseado = texto_parseado.replace(",", ".")
        texto_parseado = texto_parseado.replace(" .", ".").replace(". ", ".")
        
        # 4. Intentamos casteo matemático a Entero
        try:
            val = int(texto_parseado)
            return str(val), val
        except ValueError:
            pass
        
        # 5. Intentamos casteo matemático a Decimal (Float)
        try:
            val = float(texto_parseado)
            return str(val), val
        except ValueError:
            pass
            
        # 6. Si falla todo, es texto puro: lo pasamos por el filtro para quitar tildes
        texto_limpio = self._normalizar_texto(texto, es_variable=False)
        return f'"{texto_limpio}"', texto_limpio

    def _gestionar_variable_voz(self, tipo_bloque, contexto=""):
        from core.audio import GestorVoz

        intro = f"Para {contexto}. " if contexto else ""

        if not self.memoria_variables:
            nombre = self.voice_manager.bucle_confirmacion_voz(f"{intro}Dime el nombre de la variable")
            return self._normalizar_texto(nombre, es_variable=True)

        ultima_var = list(self.memoria_variables[-1].keys())[0]

        GestorVoz.leer_texto(f"{intro}¿Quieres usar la última variable declarada, llamada {ultima_var}?")
        resp1 = self.voice_manager.escuchar_dictado_sincrono()
        
        if resp1 and ("sí" in resp1 or "si" in resp1 or "claro" in resp1):
            return ultima_var

        resp2 = ""
        if len(self.memoria_variables) > 1:
            GestorVoz.leer_texto("¿Quieres usar otra de las variables anteriores guardadas?")
            resp2 = self.voice_manager.escuchar_dictado_sincrono()
        
        if resp2 and ("sí" in resp2 or "si" in resp2 or "claro" in resp2):
            ultimo_intento = ""
            while True:
                GestorVoz.leer_texto("Dime el nombre de la variable para poder buscarla.")
                texto_busqueda = self.voice_manager.escuchar_dictado_sincrono()
                
                if not texto_busqueda:
                    continue
                
                if "pasar" in texto_busqueda or "omitir" in texto_busqueda:
                    texto_final = ultimo_intento if ultimo_intento else texto_busqueda
                    return self._normalizar_texto(texto_final, es_variable=True)

                ultimo_intento = texto_busqueda
                texto_busqueda_norm = self._normalizar_texto(texto_busqueda, es_variable=True)

                for var_dict in self.memoria_variables:
                    nombre_var = list(var_dict.keys())[0]
                    if texto_busqueda_norm == nombre_var:
                        return nombre_var
                
                GestorVoz.leer_texto("No he encontrado esa variable en la memoria. Volvamos a intentarlo.")

        if tipo_bloque == "declaracion_var":
            nombre = self.voice_manager.bucle_confirmacion_voz(f"{intro}Dime el nombre de la variable")
            return self._normalizar_texto(nombre, es_variable=True)
        
        return ultima_var

    def _manejar_declaracion(self, tokens):
        if self.voice_manager and self.activar_voz_variables:
            nombre = self._gestionar_variable_voz("declaracion_var", contexto="declarar una variable nueva")
            valor_texto = self.voice_manager.bucle_confirmacion_voz(f"Dime el valor para {nombre}")
            codigo_valor, valor_real = self._aplicar_tipado(valor_texto)
            
            self.memoria_variables.append({nombre: valor_real})
            tokens.clear() 
            return f"{nombre} = {codigo_valor}"
        else:
            self.contador_var += 1
            resto_de_la_fila = self._consumir_argumento_vc(tokens)
            return f"var_{self.contador_var} = {resto_de_la_fila}"

    def _manejar_asignacion(self, tokens, contexto=""):
        if self.voice_manager and self.activar_voz_variables:
            pregunta = f"Para {contexto}, dime el valor" if contexto else "Dime el valor"
            valor_texto = self.voice_manager.bucle_confirmacion_voz(pregunta)
            codigo_valor, _ = self._aplicar_tipado(valor_texto)
            return codigo_valor
        else:
            return f"val_{self.contador_var}"

    def _manejar_referencia(self, tokens, contexto=""):
        if self.voice_manager and self.activar_voz_variables:
            return self._gestionar_variable_voz("referencia_var", contexto)
        else:
            return f"var_{self.contador_var}"
            
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
                if elem == "": num_tabs_fisicos += 1
                else: break
            
            tokens = [e for e in fila if e != ""]
            if not tokens: continue

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
        if not tokens: return ""
        
        primer_bloque = tokens.pop(0)
        
        if self._es_valor_numerico(primer_bloque):
            info = {"codigo": str(primer_bloque), "tipo": "valor"}
        else:
            info = self.tabla_simbolos.get(primer_bloque, {})
        
        if not info:
            return f"# ERROR_SINTAXIS: Bloque '{primer_bloque}' desconocido #"
            
        tipo = info.get("tipo", "")
        codigo_base = info.get("codigo", str(primer_bloque))
        
        if tipo == "declaracion_var":
            return self._manejar_declaracion(tokens)
        elif tipo == "asignacion_val":
            return self._manejar_asignacion(tokens, contexto="una orden general")
        elif tipo == "referencia_var":
            return self._manejar_referencia(tokens, contexto="una orden general")

        if tipo == "control_metodo":
            if not tokens: return f"# ERROR: '{primer_bloque}' necesita un sujeto a su derecha"
            sujeto = self._consumir_argumento_vc(tokens, contexto=f"el método de control de {primer_bloque}")
            if codigo_base.endswith(")"): return f"if {sujeto}{codigo_base}:"
            else: return f"if {sujeto}{codigo_base}():"

        elif tipo == "control_funcion":
            if not tokens: return f"# ERROR: '{primer_bloque}' necesita un argumento a su derecha"
            arg = self._consumir_argumento_vc(tokens, contexto=f"la función {primer_bloque}")
            return f"if {codigo_base}({arg}):"

        elif tipo == "metodo":
            if not tokens: return f"# ERROR: '{primer_bloque}' necesita un sujeto a su derecha"
            sujeto = self._consumir_argumento_vc(tokens, contexto=f"el sujeto de {primer_bloque}")
            num_args = info.get("args", 0)
            args_extra = []
            for _ in range(num_args):
                if tokens:
                    args_extra.append(self._consumir_argumento_vc(tokens, contexto=f"el argumento de {primer_bloque}"))
                    
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
                    args.append(self._consumir_argumento_vc(tokens, contexto=f"el argumento de {primer_bloque}"))
            return f"{codigo_base}({', '.join(args)})"
            
        elif tipo == "control":
            condicion = ""
            if tokens:
                condicion = self._consumir_argumento_vc(tokens, contexto=f"la condición de {primer_bloque}")
            codigo_limpio = codigo_base.replace(":", "").strip()
            if condicion: return f"{codigo_limpio} {condicion}:"
            else: return f"{codigo_limpio}:"
                
        else:
            tokens.insert(0, primer_bloque)
            return self._consumir_argumento_vc(tokens, contexto=f"el bloque junto a {primer_bloque}")

    def _consumir_argumento_vc(self, tokens, contexto=""):
        if not tokens: return ""
        
        val = tokens.pop(0)
        
        if self._es_valor_numerico(val):
            resultado = str(val)
        else:
            info = self.tabla_simbolos.get(val, {})
            tipo_val = info.get("tipo", "")
            
            if tipo_val == "referencia_var":
                resultado = self._manejar_referencia(tokens, contexto)
            elif tipo_val == "asignacion_val":
                resultado = self._manejar_asignacion(tokens, contexto)
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
                    resultado += self._consumir_argumento_vc(tokens, contexto)
                break
                
            elif tipo_sig == "metodo":
                metodo = tokens.pop(0)
                codigo_metodo = sig_info.get("codigo", metodo)
                
                num_args = sig_info.get("args", 0)
                args_extra = []
                for _ in range(num_args):
                    if tokens:
                        args_extra.append(self._consumir_argumento_vc(tokens, contexto=f"el argumento de {metodo}"))
                        
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