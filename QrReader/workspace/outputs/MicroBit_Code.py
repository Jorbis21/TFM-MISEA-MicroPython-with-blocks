from microbit import *
import speech
import music
import random
from math import *

# --- Sonido de inicialización ---
music.pitch(587, 100)
music.pitch(698, 100)
music.pitch(783, 100)

# --- Programa Principal ---
while True:
    if button_a.is_pressed():
        print('TTS:' + str(0))
        display.scroll(0)
