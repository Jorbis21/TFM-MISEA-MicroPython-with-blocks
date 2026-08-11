import json, os, subprocess, sys

class CodeManager:

    def __init__(self, state_dir, code_dir):
        self.state_dir = state_dir
        self.code_dir = code_dir

    def save_state(self, super_matrix, history):
        """Guarda el estado del codigo creado"""
        """Saves the state of the generated code"""
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
        """Carga el estado guardado del codigo"""
        """Loads the state of the saved code"""
        if os.path.exists(self.state_dir):
            try:
                with open(self.state_dir, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    return st.get("matrix", []), st.get("history", [])
            except Exception as e:
                print(f"Error cargando estado: {e}")
        return [], []

    def save_edited_code(self, new_code, pitches_block):
        """Guarda el código editado"""
        """Saves the edited code"""
        edited_lines = new_code.split('\n')
        idx_insert = 0
        for i, line in enumerate(edited_lines):
            if line.startswith("import ") or line.startswith("from "):
                idx_insert = i + 1
            else:
                break
        final_lines = edited_lines[:idx_insert] + pitches_block + edited_lines[idx_insert:]
        code_to_save = "\n".join(final_lines)
            
        try:
            with open(self.code_dir, "w", encoding="utf-8") as f:
                f.write(code_to_save)
            return True, None
        except Exception as e:
            return False, str(e)

    def read_code(self):
        try:
            with open(self.code_dir, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def upload(self):
        """Metodo para cargar el codigo en la placa"""
        """Method to load the program on the board"""
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {self.code_dir}")
        try:
            subprocess.run([sys.executable, "-m", "uflash", self.code_dir], check=True, capture_output=True, text=True)
            return True, "Código subido con éxito"
        except subprocess.CalledProcessError as e:
            print(f"Error al intentar comunicarse con uflash: {e}")
            return False, "Atención. No se detecta la placa Micro bit conectada. Revisa el cable USB."
        except FileNotFoundError:
            return False, "Error. No se encuentra Python o uflash en el sistema."