from PyQt6.QtCore import QObject, pyqtSignal


class _MainThreadDispatcher(QObject):
    """
    QObject creado en el hilo principal. Su señal se conecta a un slot propio;
    como Qt entrega las señales por cola cuando el emisor y el receptor viven
    en hilos distintos, emitir desde cualquier hilo hace que _run() se ejecute
    en el hilo dueño de este objeto (el principal), sin importar desde dónde
    se emita.
    """
    _invoke = pyqtSignal(object, tuple, dict)

    def __init__(self):
        super().__init__()
        self._invoke.connect(self._run)

    def _run(self, func, args, kwargs):
        func(*args, **kwargs)


_dispatcher = None


def init_main_thread_dispatcher():
    """
    Debe llamarse una sola vez desde el hilo principal, después de crear
    QApplication (main.py es el sitio natural). Si no se llama, run_on_main_thread
    lanza RuntimeError en vez de fallar en silencio o ejecutar en el hilo equivocado.
    """
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = _MainThreadDispatcher()


def run_on_main_thread(func, *args, **kwargs):
    """
    Programa func(*args, **kwargs) para que se ejecute en el hilo principal de Qt,
    sin importar desde qué hilo se llame a esta función. Úsalo para cualquier
    callback que vaya a tocar un widget y que pueda dispararse desde un
    threading.Thread (comandos de voz, hilos de IA, generación de PDF, etc.).
    """
    if _dispatcher is None:
        raise RuntimeError(
            "init_main_thread_dispatcher() no se ha llamado todavía "
            "(debe llamarse en main.py justo después de crear QApplication)."
        )
    _dispatcher._invoke.emit(func, args, kwargs)