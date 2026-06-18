import os
import time
import pygame
import threading
from datetime import datetime, timedelta

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ALARM_PATH = os.path.join(_BASE_DIR, "audio", "alarm.mp3")

class AlarmTool:

    def __init__(self):
        self.hilo = None
        self.alarm_active = False
        self.alarm_volume = 0.3
        self.low_volume = 0.08
        self.auto_stop_seconds = 40

    def set_alarm(self, seconds, minutes=0, hour=0,):
        tiempo_total = seconds + (minutes * 60) + (hour * 3600)
        time.sleep(tiempo_total)
        self.tocar_alarma()
        
    def tocar_alarma(self):
        pygame.mixer.init()
        pygame.mixer.music.load(_ALARM_PATH)
        # Reproducir en bucle
        pygame.mixer.music.play(-1)
        # Ajustar el volumen 
        pygame.mixer.music.set_volume(self.alarm_volume)
        self.alarm_active = True
        
        inicio = time.time()
        while pygame.mixer.music.get_busy():
            if time.time() - inicio >= self.auto_stop_seconds:
                self.stop_alarm()
                break
            pygame.time.Clock().tick(10)  
        
    def stop_alarm(self):
        pygame.mixer.music.stop()
        self.alarm_active = False

    def start_alarm(self, seconds, minutes=0, hour=0):
        tiempo_total = seconds + (minutes * 60) + (hour * 3600)
        if tiempo_total <= 0:
            print("Tiempo de alarma invalido.")
            return False

        self.hilo = threading.Thread(target=self.set_alarm, args=(seconds, minutes, hour), daemon=True)
        self.hilo.start()
        return True

    def snooze_alarm(self, seconds, minutes=0, hour=0):
        self.stop_alarm()
        time.sleep(seconds + (minutes * 60) + (hour * 3600))
        self.tocar_alarma()
        
    def alarm_at(self, hour, minutes=0, period=""):
        try:
            ahora = datetime.now()
            hour = int(hour)
            minutes = int(minutes)
            period = period.strip().lower()

            if period:
                if period == "pm" and hour < 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0

                objetivo = ahora.replace(hour=hour, minute=minutes, second=0, microsecond=0)

                if objetivo <= ahora:
                    objetivo += timedelta(days=1)
            else:
                candidatos = []

                if hour == 12:
                    horas_posibles = [0, 12]
                elif 1 <= hour <= 11:
                    horas_posibles = [hour, hour + 12]
                else:
                    horas_posibles = [hour]

                for hora_posible in horas_posibles:
                    candidato = ahora.replace(hour=hora_posible, minute=minutes, second=0, microsecond=0)
                    if candidato <= ahora:
                        candidato += timedelta(days=1)
                    candidatos.append(candidato)

                objetivo = min(candidatos)
                hour = objetivo.hour

            diferencia = objetivo - ahora
            segundos_totales = int(diferencia.total_seconds())
            print(f"Alarma programada para las {hour:02d}:{minutes:02d}. Suena en {segundos_totales} segundos.")
            self.start_alarm(segundos_totales)
            return True
        except Exception:
            return False
