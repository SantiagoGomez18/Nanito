import time
import pygame
import threading

class AlarmTool:

    def set_alarm(self, seconds, minutes=0, hour=0,):
        tiempo_total = seconds + (minutes * 60) + (hour * 3600)
        time.sleep(tiempo_total)
        self.tocar_alarma()
        
    def tocar_alarma(self):
        pygame.mixer.init()
        pygame.mixer.music.load("audio/alarm.mp3")
        pygame.mixer.music.play(-1) # Reproducir en bucle
        pygame.mixer.music.set_volume(0.3)  # Ajustar el volumen (0.0 a 1.0)
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)  # Esperar a que termine la música
        
    def stop_alarm(self):
        pygame.mixer.music.stop()
        
    def start_alarm(self, seconds, minutes=0, hour=0):
        hilo = threading.Thread(target=self.set_alarm, args=(seconds, minutes, hour))
        hilo.start()

    def snooze_alarm(self, seconds, minutes=0, hour=0):
        self.stop_alarm()
        time.sleep(seconds + (minutes * 60) + (hour * 3600))
        self.tocar_alarma()
