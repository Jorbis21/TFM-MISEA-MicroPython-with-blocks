import os, sys
from PyQt6.QtWidgets import QApplication
from controllers.app_controller import AppController

def main():
    # SOLUCIÓN: Añadimos '..' para que suba un nivel (saliendo de src/) 
    # y se sitúe en la raíz del proyecto.
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Ahora todas estas rutas se construirán correctamente
    workspace_dir = os.path.join(base_dir, 'workspace') 
    config_dir = os.path.join(base_dir, 'data', 'config')
    assets_dir = os.path.join(base_dir, 'data', 'assets')

    os.makedirs(os.path.join(workspace_dir, 'inputs'), exist_ok=True)
    os.makedirs(os.path.join(workspace_dir, 'outputs'), exist_ok=True)
    
    app = QApplication(sys.argv)
    
    controlador_principal = AppController(workspace_dir, config_dir, assets_dir)
    controlador_principal.iniciar()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()