import asyncio
import multiprocessing
import os
import tempfile
import time
import edge_tts
import pygame


def _listen_worker(device_index, timeout, phrase_time_limit, language, queue):
    # Corre en un PROCESO separado a proposito: si PortAudio/ALSA hace
    # segmentation fault al abrir el microfono, solo muere este proceso
    # hijo. El proceso principal (main.py) nunca se entera y sigue vivo.
    import speech_recognition as sr

    try:
        listener = sr.Recognizer()
        listener.pause_threshold = 2.0
        listener.non_speaking_duration = 1.0
        listener.phrase_threshold = 0.2
        listener.dynamic_energy_threshold = True

        with sr.Microphone(device_index=device_index) as source:
            listener.adjust_for_ambient_noise(source, duration=1)
            audio = listener.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

        rec = listener.recognize_google(audio, language=language)
        queue.put(("ok", rec.lower()))
    except sr.WaitTimeoutError:
        queue.put(("timeout", None))
    except sr.UnknownValueError:
        queue.put(("unknown", None))
    except sr.RequestError as e:
        queue.put(("request_error", str(e)))
    except Exception as e:
        queue.put(("error", str(e)))


class VoiceTool:
    def __init__(self, device_index=None, timeout=10):
        # device_index=None deja que SpeechRecognition use el microfono por
        # defecto del sistema. Con un unico microfono conectado, la
        # deteccion por nombre resultaba en indices inconsistentes en
        # Raspberry Pi OS (la cuenta de dispositivos cambia entre el
        # escaneo y la apertura real del stream).
        self.device_index = device_index
        self.timeout = timeout
        self.phrase_time_limit = 20
        self.language = "es-CO"
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
        if show_status:
            print("Escuchando...")

        queue = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=_listen_worker,
            args=(self.device_index, self.timeout, self.phrase_time_limit, self.language, queue),
            daemon=True
        )
        proc.start()
        proc.join(timeout=self.timeout + 15)

        if proc.is_alive():
            proc.terminate()
            proc.join()
            if show_errors:
                print("El microfono no respondio a tiempo, se omite este intento.")
            return ""

        if proc.exitcode != 0:
            if show_errors:
                print(f"El proceso de escucha fallo (codigo {proc.exitcode}), se omite este intento.")
            return ""

        try:
            status, data = queue.get_nowait()
        except Exception:
            return ""

        if status == "ok":
            if show_status:
                print(f"Comando reconocido: {data}")
            return data
        if status == "timeout":
            if show_errors:
                print(f"No se detecto voz en {self.timeout} segundos.")
        elif status == "unknown":
            if show_errors:
                print("No se entendio el audio.")
        elif status == "request_error":
            if show_errors:
                print(f"Error del servicio de reconocimiento: {data}")
        else:
            if show_errors:
                print(f"Error al reconocer el comando: {data}")
        return ""
