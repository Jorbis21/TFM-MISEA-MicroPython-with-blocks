from microbit import *
import speech
import music

while True:
	if  button_a.is_pressed():
		music.play(music.BIRTHDAY)
	if  button_b.is_pressed():
		display.show(Image.ALL_CLOCKS)
	if accelerometer.is_gesture('shake'):
		audio.play(Sound.GIGGLE)
