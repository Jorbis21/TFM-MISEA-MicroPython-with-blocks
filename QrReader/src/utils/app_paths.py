import sys
import os


def get_resource_dir():
    """
        Devuelve la carpeta desde la que se deben LEER los recursos empaquetados
        con la aplicacion (iconos, estilos, blocks_es/en.json de fabrica, cache
        de voz pre-generada): cosas que nunca se escriben en tiempo de ejecucion.
        - Ejecutando desde codigo fuente: la raiz del proyecto.
        - Empaquetado con PyInstaller: sys._MEIPASS, la carpeta real donde
          PyInstaller coloca los datos empaquetados. Es DISTINTA de donde esta
          el .exe: en modo --onedir suele ser una subcarpeta _internal/, y en
          --onefile es la carpeta temporal de extraccion.
    """
    """
        Returns the folder to READ the resources bundled with the app from
        (icons, styles, factory blocks_es/en.json, pre-generated voice cache):
        things that never get written to at runtime.
        - Running from source: the project root.
        - Packaged with PyInstaller: sys._MEIPASS, the real folder where
          PyInstaller places the bundled data. It's DIFFERENT from where the
          .exe is: in --onedir mode it's usually an _internal/ subfolder, and
          in --onefile it's the temporary extraction folder.
    """
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def get_data_dir():
    """
        Devuelve la carpeta donde debe vivir lo que la aplicacion necesita
        ESCRIBIR y que tiene que persistir entre ejecuciones (settings.json,
        workspace/): la raiz del proyecto al ejecutar desde codigo fuente, o
        la carpeta donde esta el .exe al ir empaquetado — nunca la carpeta
        temporal de extraccion de PyInstaller, que se borra en cada arranque
        y haria perder la configuracion y el workspace entre una ejecucion y
        la siguiente.
    """
    """
        Returns the folder where whatever the app needs to WRITE and persist
        across runs should live (settings.json, workspace/): the project root
        when running from source, or the folder containing the .exe when
        packaged — never PyInstaller's temporary extraction folder, which
        gets wiped on every launch and would lose the config and workspace
        between runs.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))