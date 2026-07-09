import os
import json
import subprocess
import sys

class MicrobitCompiler:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        # Hash Map maestro O(1)
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
        """
        Determina si un token debe tratarse como un número.
        Es agnóstico a la fuente: funciona igual si viene de un QR,
        de texto o de voz.
        """
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

        # LA PILA (Stack): Controla el alcance vertical (Scopes)
        pila_contexto = []

        for fila in matriz_comandos:
            # 1. Análisis Léxico: Separar indentación de los tokens útiles
            num_tabs_fisicos = 0
            for elem in fila:
                if elem == "":
                    num_tabs_fisicos += 1
                else:
                    break
            
            tokens = [e for e in fila if e != ""]
            if not tokens:
                continue

            # 2. Gestión de Pila (Pushdown Automaton logic)
            # Si la indentación física baja, sacamos contextos de la pila
            while len(pila_contexto) > num_tabs_fisicos:
                pila_contexto.pop()

            linea_str = "\t" * num_tabs_fisicos
            
            # 3. MÁQUINA DE ESTADOS FINITA (Autómata Horizontal)
            estado = "INICIO"
            args_pendientes = 0
            
            for token in tokens:
                # Recuperar el nodo de la tabla de símbolos (O(1))
                if self._es_valor_numerico(token):
                    nodo = {"codigo": token, "tipo": "valor"}
                else:
                    nodo = self.tabla_simbolos.get(token)
                    if not nodo:
                        linea_str += f"# ERROR_SINTAXIS: Bloque '{token}' desconocido #"
                        break

                # --- TRANSICIONES DE ESTADO ---
                if estado == "INICIO":
                    if nodo["tipo"] == "control":
                        linea_str += nodo["codigo"]
                        pila_contexto.append("BLOQUE_CONTROL") # Push a la pila
                        
                    elif nodo["tipo"] == "funcion":
                        linea_str += nodo["codigo"] + "("
                        args_pendientes = nodo.get("args", 0)
                        if args_pendientes > 0:
                            estado = "ESPERANDO_ARG"
                        else:
                            linea_str += ")"
                            
                    elif nodo["tipo"] == "sujeto":
                        linea_str += nodo["codigo"]
                        estado = "ESPERANDO_METODO"

                elif estado == "ESPERANDO_ARG":
                    if nodo["tipo"] == "valor":
                        linea_str += nodo["codigo"]
                        args_pendientes -= 1
                        if args_pendientes == 0:
                            linea_str += ")"
                            estado = "INICIO"
                        else:
                            linea_str += ", "
                    else:
                        linea_str += f" # ERROR: Se esperaba un Valor, se recibió {nodo['tipo']}"
                        break

                elif estado == "ESPERANDO_METODO":
                    if nodo["tipo"] == "metodo":
                        # Verificación de compatibilidad (Tipado fuerte)
                        if nodo.get("requiere") and nodo["requiere"] != self.tabla_simbolos.get(tokens[0], {}).get("clase"):
                            linea_str += f" # ERROR: El método no es compatible con el sujeto"
                        else:
                            linea_str += nodo["codigo"]
                            pila_contexto.append("BLOQUE_METODO") # Push a la pila
                        estado = "INICIO"
                        
                    elif nodo["tipo"] == "operador_logico":
                        linea_str += nodo["codigo"]
                        estado = "INICIO"

            # 4. Cierre de línea y volcado
            codigo_final.append(linea_str)

        # Escritura a disco
        with open(ruta_salida, "w", encoding="utf-8") as file:
            file.write("\n".join(codigo_final) + "\n")

        print("Código compilado con éxito mediante Autómata de Pila.")

    def subir(self, ruta_codigo):
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {ruta_codigo}")
        try:
            subprocess.run([sys.executable, "-m", "uflash", ruta_codigo], check=True)
            print("¡Código subido con éxito a la micro:bit!")
        except subprocess.CalledProcessError as e:
            print(f"Error al intentar comunicarse con uflash: {e}")
        except FileNotFoundError:
            print("Error: No se encuentra Python o uflash en el sistema.")