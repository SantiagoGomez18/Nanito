import asyncio
import os
import tempfile
import time
import edge_tts
import pygame
import speech_recognition as sr


def _find_input_device():
    nombres = sr.Microphone.list_microphone_names()
    for i, nombre in enumerate(nombres):
        n = nombre.lower()
        if any(k in n for k in ("usb", "respeaker", "jounivo", "microphone", "mic")):
            return i
    return None  # None deja que SpeechRecognition use el microfono por defecto


class VoiceTool:
    def __init__(self, device_index=None, timeout=10):
        self.device_index = device_index if device_index is not None else _find_input_device()
        print(f"Microfono seleccionado: index={self.device_index}")
        self.timeout = timeout
        self.listener = sr.Recognizer()
        self.listener.pause_threshold = 2.0
        self.listener.non_speaking_duration = 1.0
        self.listener.phrase_threshold = 0.2
        self.listener.dynamic_energy_threshold = True
        self.phrase_time_limit = 20
        self.voice_name = "es-MX-JorgeNeural"
        self.voice_rate = "+0%"

        if not pygame.mixer.get_init():
            pygame.mixer.init()

    async def texto_a_audio(self, text, output_path):
        communicate = edge_tts.Communicate(text=text, voice=self.voice_name, rate=self.voice_rate)
        await communicate.save(output_path)

    def talk(self, text):
        if not text:
            return

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_path = temp_file.name

            asyncio.run(self.texto_a_audio(text, temp_path))

            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            print(f"Error al reproducir la voz: {e}")
        finally:
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass

            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def listen(self, show_status=True, show_errors=True):
        try:
            with sr.Microphone(device_index=self.device_index) as source:
                if show_status:                    
                    print("Escuchando...")
                    
                self.listener.adjust_for_ambient_noise(source, duration=1)
                pc = self.listener.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit
                )
                rec = self.listener.recognize_google(pc, language='es-ES')
                if show_status:
                    print(f"Comando reconocido: {rec}")
                return rec.lower()
        except sr.WaitTimeoutError:
            if show_errors:
                print(f"No se detecto voz en {self.timeout} segundos.")
        except sr.UnknownValueError:
            if show_errors:
                print("No se entendio el audio.")
        except sr.RequestError as e:
            if show_errors:
                print(f"Error del servicio de reconocimiento: {e}")
        except Exception as e:
            if show_errors:
                print(f"Error al reconocer el comando: {e}")
        return ""
