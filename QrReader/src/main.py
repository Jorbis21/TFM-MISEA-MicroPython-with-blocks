import os
import sys
from PyQt6.QtWidgets import QApplication
from gui.app_window import AppCamara

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    workspace_dir = os.path.join(base_dir, 'workspace') 
    config_dir = os.path.join(base_dir, 'data', 'config')
    assets_dir = os.path.join(base_dir, 'data', 'assets')

    os.makedirs(os.path.join(workspace_dir, 'inputs'), exist_ok=True)
    os.makedirs(os.path.join(workspace_dir, 'outputs'), exist_ok=True)
    
    # 1. Arrancar el motor de la aplicación PyQt6
    app = QApplication(sys.argv)
    
    # 2. Instanciar tu orquestador (la ventana principal)
    ventana = AppCamara(workspace_dir=workspace_dir, config_dir=config_dir, assets_dir = assets_dir)
    
    # 3. Hacer visible la ventana
    ventana.show()
    
    # 4. Iniciar el bucle de eventos (mantiene el programa abierto)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()