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
casa = "madrid"
numero = 1492
while True:
    if button_a.is_pressed():
        display.show(numero)
    if button_b.is_pressed():
        display.scroll(casa)
