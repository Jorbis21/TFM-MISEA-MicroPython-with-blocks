from enum import Enum

class VoiceCommand(Enum):
    """Acciones que se pueden disparar por voz o por atajo de teclado, mapeadas a los métodos de acción de la pestaña de cámara"""
    """Actions that can be triggered by voice or keyboard shortcut, mapped to the camera tab's action methods"""
    CAPTURE = "capture"
    SEND = "send"
    EXPLAIN = "explain"
    READ = "read"
    CHANGE_TTS = "change_tts"
    REVIEW = "review"

class TTSMode(Enum):
    """Modo de lectura en voz alta de los valores mostrados en pantalla: por el PC, por la propia placa, o apagado"""
    """Voice-reading mode for the values shown on screen: through the PC, through the board itself, or off"""
    PC = "pc"
    BOARD = "board"
    SHUTDONW = "off"

class EventType(Enum):
    """Tipo de evento de interacción recibido: dicho por voz, un toque físico de confirmación, u omitido"""
    """Type of interaction event received: spoken by voice, a physical confirmation tap, or skipped"""
    VOICE = "voice"
    TAP = "tap"
    SKIP = "skip"