import json, os
from utils.strings import t

class CodeManager:
    """Guarda y recupera el estado del programa (la matriz de bloques y su historial) y el código MicroPython generado, en disco"""
    """Saves and recovers the program's state (the block matrix and its history) and the generated MicroPython code, on disk"""

    def __init__(self, state_dir, code_dir):
        """Guarda las rutas de los dos archivos que gestiona: el del estado (json) y el del código generado (.py)"""
        """Stores the paths of the two files it manages: the state one (json) and the generated code one (.py)"""
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
            return True, None
        except Exception as e:
            print(f"Error guardando estado: {e}")
            return False, str(e)

    def load_state(self):
        """Carga el estado guardado del codigo"""
        """Loads the state of the saved code"""
        if os.path.exists(self.state_dir):
            try:
                with open(self.state_dir, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    return st.get("matrix", []), st.get("history", []), None
            except Exception as e:
                print(f"Error cargando estado: {e}")
                return [], [], str(e)
        return [], [], None

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
        """Lee el código generado del disco; devuelve None si todavía no se ha generado ninguno"""
        """Reads the generated code from disk; returns None if none has been generated yet"""
        try:
            with open(self.code_dir, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def get_display_code(self):
        """Obtiene el codigo tal como se debe mostrar en el editor, separando el bloque de sonidos de inicializacion, y comprueba su sintaxis"""
        """Gets the code as it should be displayed in the editor, separating the initialization sounds block, and checks its syntax"""
        code = self.read_code()

        if code is None:
            return t("code_not_generated"), t("status_waiting_capture"), [], False

        lines = code.split('\n')
        line_cut_fin = -1
        line_cut_ini = -1
        for i, line in enumerate(lines):
            if t("marker_init_sound") in line: line_cut_ini = i
            if t("marker_main_program") in line:
                line_cut_fin = i
                break

        pitches_block = []
        if line_cut_ini != -1 and line_cut_fin != -1:
            visible_lines = []
            for i, line in enumerate(lines):
                if i < line_cut_ini: visible_lines.append(line)
                elif i >= line_cut_ini and i <= line_cut_fin: pitches_block.append(line)
                else: visible_lines.append(line)
            show_code = "\n".join(visible_lines)
        else:
            show_code = code

        state = t("status_no_syntax_errors")
        error = False
        code_to_compile = show_code.replace('\xa0', ' ').replace('\t', '    ') + '\n'

        try:
            compile(code_to_compile, '<string>', 'exec')
        except SyntaxError as e:
            state = t("status_syntax_error", lineno=e.lineno)
            error = True

        return show_code, state, pitches_block, error

    def save_manual_code(self, new_code, pitches_block):
        """Guarda el codigo modificado manualmente desde el editor"""
        """Saves the code manually modified from the editor"""
        clean_code = new_code.replace('\xa0', ' ').replace('\t', '    ')
        return self.save_edited_code(clean_code, pitches_block)

    def upload(self):
        """Metodo para cargar el codigo en la placa"""
        """Method to load the program on the board"""
        print(f"Iniciando el flasheo en la micro:bit con el archivo: {self.code_dir}")
        
        try:
            import uflash
        except ImportError as e:
            print(f"uflash no está disponible como módulo: {e}")
            return False, t("upload_error_missing_module")

        try:
            uflash.flash(path_to_python=self.code_dir)
            return True, t("upload_success")
        except IOError as e:
            print(f"No se pudo flashear (¿placa no conectada?): {e}")
            return False, t("upload_error_no_board")
        except Exception as e:
            print(f"Error inesperado al flashear: {e}")
            return False, t("upload_error_no_board")