from enum import Enum

class VoiceCommand(Enum):
    CAPTURE = "capturar"
    SEND = "enviar"
    EXPLAIN = "explicar"
    READ = "leer"
    CHANGE_TTS = "cambiar_tts"
    REVIEW = "repasar"

class TTSMode(Enum):
    PC = "pc"
    BOARD = "board"
    SHUTDONW = "apagado"

class EventType(Enum):
    VOICE = "voz"
    TAP = "toque_fisico"
    SKIP = "omitir"