import json
import os
import sys
import subprocess

class MicrobitTranslator:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.archives = ["basic", "input", "demo"]
        self.data_consolidada = self._cargar_jsons()

    def _cargar_jsons(self):
        data = []
        for arch in self.archives:
            ruta_json = os.path.join(self.config_dir, f'{arch}.json')
            try:
                with open(ruta_json, 'r', encoding='utf-8') as f:
                    data.append(json.load(f))
            except FileNotFoundError:
                print(f"Advertencia: No se encontró {ruta_json}")
        return data

    def _buscar_en_json(self, comando):
        for d in self.data_consolidada:
            for categoria in ["functions", "conditionals", "variables"]:
                for f in d.get(categoria, []):
                    if f.get("funcBit") == comando:
                        return (f, "funcion")
                    if f.get("condType") == comando:
                        return (f, "condicion")
                    if f.get("varType") == comando:
                        return (f, "variable")
        return None

    def generar_codigo(self, lista_comandos, ruta_salida):
        if not lista_comandos:
            print("No se recibieron comandos para traducir.")
            return

        with open(ruta_salida, "w", encoding="utf-8") as file:
            file.write("from microbit import *\n\n")
            
            nivel_identacion = 0
            comando_abierto = False
            str_cierre = ""
            linea_actual = "" 

            def escribir(texto):
                nonlocal nivel_identacion, linea_actual
                file.write(texto)
                linea_actual += texto
                if "\n" in linea_actual:
                    partes = linea_actual.split("\n")
                    for i in range(len(partes) - 1):
                        if partes[i].strip().endswith(":"):
                            nivel_identacion += 1
                    linea_actual = partes[-1]

            for comando in lista_comandos:
                if comando.lower() == "end":
                    if comando_abierto:
                        escribir(str_cierre)
                        comando_abierto = False
                    nivel_identacion = max(0, nivel_identacion - 1)
                    continue
                
                if comando.lower() == "on start" and nivel_identacion > 0:
                    print("Advertencia: 'on start' no puesto al principio")
                    return
                    
                es_numero = comando.isdigit() or (comando.replace('.', '', 1).isdigit() and comando.count('.') < 2)
                if es_numero:
                    escribir(f"{comando}")
                    continue 

                func_data = self._buscar_en_json(comando)
                
                if func_data:
                    data_json = func_data[0]
                    tipo_comando = func_data[1]

                    if tipo_comando == "funcion":
                        if comando_abierto:
                            escribir(str_cierre)
                            comando_abierto = False
                                
                        tabulaciones = "\t" * nivel_identacion
                        codigo_ini = data_json.get('funcPyIni', '')
                        escribir(f"{tabulaciones}{codigo_ini}")
                        
                        str_cierre = data_json.get('funcPyFin', '') + "\n"
                        comando_abierto = True
                        
                    elif tipo_comando == "condicion":
                        condicion = data_json.get('cond', '')
                        escribir(f" {condicion} ")
                        
                    elif tipo_comando == "variable":
                        valor = data_json.get('var', '')
                        is_val_number = valor.isdigit() or (valor.replace('.', '', 1).isdigit() and valor.count('.') < 2)
                        if valor and not valor.startswith("Image.") and not is_val_number:
                            valor = f"'{valor}'"
                        escribir(f"{valor}")
                else:
                    print(f"Comando '{comando}' no reconocido.")

            if comando_abierto:
                escribir(str_cierre)

        print(f"Código generado con éxito. Nivel final de identación: {nivel_identacion}")

    def subir(self, ruta_codigo):
        """Flashea el código generado en la Micro:bit usando subprocess."""
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {ruta_codigo}")
        
        try:
            # subprocess.run toma una lista de argumentos y maneja TODAS las comillas 
            # y espacios en blanco de las rutas de forma automática y segura por debajo.
            subprocess.run([sys.executable, "-m", "uflash", ruta_codigo], check=True)
            
            print("¡Código subido con éxito a la micro:bit!")
            
        except subprocess.CalledProcessError as e:
            print(f"Error al intentar comunicarse con uflash: {e}")
        except FileNotFoundError:
            print("Error: No se encuentra Python o uflash en el sistema.")