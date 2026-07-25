import asyncio
import os
import tempfile
import threading
import time
import edge_tts
import pygame
import speech_recognition as sr


class VoiceTool:
    def __init__(self, device_index=None, timeout=10):
        # device_index=None deja que SpeechRecognition use el microfono por
        # defecto del sistema. Con un unico microfono conectado, la
        # deteccion por nombre resultaba en indices inconsistentes en
        # Raspberry Pi OS (la cuenta de dispositivos cambia entre el
        # escaneo y la apertura real del stream).
        self.device_index = device_index
        print(f"Microfono seleccionado: index={self.device_index} (por defecto del sistema)")
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

    def _listen_blocking(self, show_status, show_errors, result_holder):
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
                rec = self.listener.recognize_google(pc, language='es-CO')
                if show_status:
                    print(f"Comando reconocido: {rec}")
                result_holder["text"] = rec.lower()
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

    def listen(self, show_status=True, show_errors=True):
        # Timeout duro a nivel de hilo: si la captura de audio se cuelga
        # (driver ALSA, mic desconectado, etc.), el propio timeout interno
        # de speech_recognition no puede salvarnos porque el bloqueo ocurre
        # en una lectura de bajo nivel. Este wrapper garantiza que el loop
        # principal nunca se congele mas del limite indicado.
        result_holder = {"text": ""}
        hilo = threading.Thread(
            target=self._listen_blocking,
            args=(show_status, show_errors, result_holder),
            daemon=True
        )
        hilo.start()
        hilo.join(timeout=self.timeout + 15)

        if hilo.is_alive():
            if show_errors:
                print("El microfono no respondio a tiempo, se omite este intento.")
            return ""

        return result_holder["text"]
