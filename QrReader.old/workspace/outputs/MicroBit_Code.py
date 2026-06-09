from microbit import *
import speech
import music

while True:
	if  button_b.is_pressed():
		audio.play(Sound.GIGGLE)
	if  button_a.is_pressed():
		display.show()
