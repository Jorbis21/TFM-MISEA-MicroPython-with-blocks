import json
import os
import sys
import subprocess

class MicrobitTranslator:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.archives = ["functions", "variables", "conditionals"]
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

    def generar_codigo(self, matriz_comandos, ruta_salida):

        if not matriz_comandos:
            print("No se recibieron comandos para traducir.")
            return

        with open(ruta_salida, "w", encoding="utf-8") as file:
            file.write("from microbit import *\nimport speech\nimport music\n\n")
            
            for fila in matriz_comandos:
                # 1. Calcular la indentación FÍSICA
                num_tabs = 0
                for elem in fila:
                    if elem == "":
                        num_tabs += 1
                    else:
                        break
                
                elementos = [e for e in fila if e != ""]
                if not elementos or elementos[0].lower() in ["end", "fin"]:
                    continue

                linea_str = "\t" * num_tabs
                stack_cierres = []  # Pila LIFO para los cierres anidados
                last_tipo = None
                
                for i, comando in enumerate(elementos):
                    # Identificar si el bloque es un número suelto
                    es_numero = comando.isdigit() or (comando.replace('.', '', 1).isdigit() and comando.count('.') < 2)
                    
                    if es_numero:
                        str_ini = str(comando)
                        str_fin = ""
                        tipo = "variable"
                    else:
                        func_data = self._buscar_en_json(comando)
                        if func_data:
                            data_json, tipo = func_data
                            
                            if tipo == "funcion":
                                str_ini = data_json.get('funcPyIni', '')
                                str_fin = data_json.get('funcPyFin', '')
                                
                                # --- CASO ESPECIAL (VISIÓN HACIA ADELANTE) ---
                                aux_fin = data_json.get('funcPyFinAux') or data_json.get('FuncPyFinAux')
                                if aux_fin:
                                    es_boton = False
                                    # Miramos el SIGUIENTE bloque en la línea física
                                    if i + 1 < len(elementos):
                                        sig_comando = elementos[i+1]
                                        sig_data = self._buscar_en_json(sig_comando)
                                        # Comprobamos si la traducción de esa variable contiene "button"
                                        if sig_data and sig_data[1] == "variable":
                                            var_py = sig_data[0].get('var', '')
                                            if 'button' in var_py.lower():
                                                es_boton = True
                                    
                                    # Si el bloque que viene después NO es un botón, usamos el cierre auxiliar
                                    if not es_boton:
                                        str_fin = aux_fin
                                # ----------------------------------------------
                                
                            elif tipo == "condicion":
                                str_ini = data_json.get('condIni', data_json.get('cond', ''))
                                str_fin = data_json.get('condFin', '')
                                
                            elif tipo == "variable":
                                str_ini = data_json.get('var', '')
                                str_fin = ""
                                is_val_number = str_ini.isdigit() or (str_ini.replace('.', '', 1).isdigit() and str_ini.count('.') < 2)
                                if str_ini and not str_ini.startswith("Image.") and not is_val_number:
                                    str_ini = f"{str_ini}"
                        else:
                            print(f"Comando '{comando}' no reconocido.")
                            str_ini = f"#{comando}#"
                            str_fin = ""
                            tipo = "desconocido"

                    # --- LÓGICA REGLAMENTARIA DE ENSAMBLAJE ---
                    prefix = ""
                    if i > 0:
                        if str_ini.startswith('.'):
                            prefix = ""
                        elif last_tipo == "variable" and tipo == "variable":
                            prefix = ", "
                        elif linea_str and not linea_str.endswith('(') and not linea_str.endswith('['):
                            prefix = " "
                            
                    linea_str += prefix + str_ini
                    
                    if str_fin:
                        stack_cierres.append(str_fin)
                        
                    last_tipo = tipo
                
                # --- CIERRE DE LA LÍNEA ---
                while stack_cierres:
                    linea_str += stack_cierres.pop()
                    
                if not linea_str.endswith('\n'):
                    linea_str += '\n'
                    
                file.write(linea_str)

        print("Código generado con éxito basado en matriz espacial.")

    def subir(self, ruta_codigo):
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {ruta_codigo}")
        try:
            subprocess.run([sys.executable, "-m", "uflash", ruta_codigo], check=True)
            print("¡Código subido con éxito a la micro:bit!")
        except subprocess.CalledProcessError as e:
            print(f"Error al intentar comunicarse con uflash: {e}")
        except FileNotFoundError:
            print("Error: No se encuentra Python o uflash en el sistema.")