import json, os, subprocess, sys

class FileManager:

    def __init__(self, state_dir, code_dir):
        self.state_dir = state_dir
        self.code_dir = code_dir

    def save_state(self, super_matrix, history):
        try:
            st = {
                "matrix": super_matrix,
                "history": history
            }
            with open(self.state_dir, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error guardando estado: {e}")

    def load_state(self):
        if os.path.exists(self.state_dir):
            try:
                with open(self.state_dir, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    return st.get("matrix", []), st.get("history", [])
            except Exception as e:
                print(f"Error cargando estado: {e}")
        return [], []

    def save_edited_code(self, nuevo_codigo, bloque_pitches):
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
            with open(self.code_dir, "w", encoding="utf-8") as f:
                f.write(codigo_a_guardar)
            return True, None
        except Exception as e:
            return False, str(e)

    def upload(self):
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {self.code_dir}")
        try:
            subprocess.run([sys.executable, "-m", "uflash", self.code_dir], check=True, capture_output=True, text=True)
            return True, "Código subido con éxito"
        except subprocess.CalledProcessError as e:
            print(f"Error al intentar comunicarse con uflash: {e}")
            # DEVOLVEMOS EL ERROR EN VEZ DE HABLARLO DIRECTAMENTE
            return False, "Atención. No se detecta la placa Micro bit conectada. Revisa el cable USB."
        except FileNotFoundError:
            return False, "Error. No se encuentra Python o uflash en el sistema."