from microbit import *
import speech
import music
import random
from math import *
music.pitch(587, 100)
music.pitch(698, 100)
music.pitch(783, 100)

# --- Programa Principal ---
texto = "alegria"
numero = 12
while True:
    if button_b.is_pressed():
        print('TTS:' + str(texto))
        display.scroll(texto)
    if button_a.is_pressed():
        print('TTS:' + str(numero))
        display.show(numero)
