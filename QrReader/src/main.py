import os
from gui.app_window import AppCamara

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    workspace_dir = os.path.join(base_dir, 'workspace')
    config_dir = os.path.join(base_dir, 'data','config')

    os.makedirs(os.path.join(workspace_dir, 'inputs'), exist_ok=True)
    os.makedirs(os.path.join(workspace_dir, 'outputs'), exist_ok=True)
    
    app = AppCamara(workspace_dir=workspace_dir, config_dir=config_dir)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

if __name__ == "__main__":
    main()