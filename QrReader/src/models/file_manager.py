import json, os, subprocess, sys

class FileManager:
    # ELIMINADO: audio_service
    def __init__(self, ruta_estado, ruta_codigo):
        self.ruta_estado = ruta_estado
        self.ruta_codigo = ruta_codigo

    def guardar_estado(self, super_matriz, historial):
        try:
            estado = {
                "matriz": super_matriz,
                "historial": historial
            }
            with open(self.ruta_estado, "w", encoding="utf-8") as f:
                json.dump(estado, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error guardando estado: {e}")

    def cargar_estado(self):
        if os.path.exists(self.ruta_estado):
            try:
                with open(self.ruta_estado, "r", encoding="utf-8") as f:
                    estado = json.load(f)
                    return estado.get("matriz", []), estado.get("historial", [])
            except Exception as e:
                print(f"Error cargando estado: {e}")
        return [], []

    def guardar_codigo_editado(self, nuevo_codigo, bloque_pitches):
        lineas_editadas = nuevo_codigo.split('\n')
        idx_insert = 0
        for i, linea in enumerate(lineas_editadas):
            if linea.startswith("import ") or linea.startswith("from "):
                idx_insert = i + 1
            else:
                break
        lineas_finales = lineas_editadas[:idx_insert] + bloque_pitches + lineas_editadas[idx_insert:]
        codigo_a_guardar = "\n".join(lineas_finales)
            
        try:
            with open(self.ruta_codigo, "w", encoding="utf-8") as f:
                f.write(codigo_a_guardar)
            return True, None
        except Exception as e:
            return False, str(e)

    def subir(self):
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {self.ruta_codigo}")
        try:
            subprocess.run([sys.executable, "-m", "uflash", self.ruta_codigo], check=True, capture_output=True, text=True)
            return True, "Código subido con éxito"
        except subprocess.CalledProcessError as e:
            print(f"Error al intentar comunicarse con uflash: {e}")
            # DEVOLVEMOS EL ERROR EN VEZ DE HABLARLO DIRECTAMENTE
            return False, "Atención. No se detecta la placa Micro bit conectada. Revisa el cable USB."
        except FileNotFoundError:
            return False, "Error. No se encuentra Python o uflash en el sistema."