# utils/constants.py
from enum import Enum

class ComandoVoz(Enum):
    CAPTURAR = "capturar"
    ENVIAR = "enviar"
    EXPLICAR = "explicar"
    LEER = "leer"
    CAMBIAR_TTS = "cambiar_tts"
    REPASAR = "repasar"

class ModoTTS(Enum):
    PC = "pc"
    PLACA = "placa"
    APAGADO = "apagado"

class TipoEvento(Enum):
    VOZ = "voz"
    TOQUE_FISICO = "toque_fisico"
    OMITIR = "omitir"