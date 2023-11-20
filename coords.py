import pyautogui
import keyboard

while True:
    keyboard.wait('space')
    pos = pyautogui.position()
    print('({}, {})'.format(pos[0], pos[1]))
