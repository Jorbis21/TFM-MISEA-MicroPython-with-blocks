from enum import Enum

class VoiceCommand(Enum):
    CAPTURE = "capture"
    SEND = "send"
    EXPLAIN = "explain"
    READ = "read"
    CHANGE_TTS = "change_tts"
    REVIEW = "review"

class TTSMode(Enum):
    PC = "pc"
    BOARD = "board"
    SHUTDONW = "off"

class EventType(Enum):
    VOICE = "voice"
    TAP = "tap"
    SKIP = "skip"