import asyncio
import multiprocessing
import os
import tempfile
import time

# edge_tts y pygame se importan de forma perezosa dentro de los metodos que
# los usan. Con el metodo "spawn", el proceso hijo re-importa este modulo en
# cada escucha; importarlos aca arriba le costaria 1-2s extra por ciclo en la
# Raspberry Pi, y el hijo no los necesita.


def _resolve_input_device(requested):
    # Busca un dispositivo de ENTRADA real en vez de confiar en el "default"
    # de ALSA. En Raspberry Pi el mic USB existe pero no siempre esta
    # configurado como default, y pedirlo con device_index=None falla con
    # "No Default Input Device Available".
    import pyaudio

    pa = pyaudio.PyAudio()
    try:
        total = pa.get_device_count()

        # Si nos pasaron un indice, lo usamos solo si es valido y es entrada.
        if requested is not None and 0 <= requested < total:
            info = pa.get_device_info_by_index(requested)
            if info.get("maxInputChannels", 0) > 0:
                return requested

        entradas = []
        for i in range(total):
            try:
                info = pa.get_device_info_by_index(i)
            except Exception:
                continue
            if info.get("maxInputChannels", 0) > 0:
                entradas.append((i, str(info.get("name", "")).lower()))

        if not entradas:
            return None

        for i, nombre in entradas:
            if any(k in nombre for k in ("jounivo", "usb", "respeaker", "mic")):
                return i

        return entradas[0][0]
    finally:
        pa.terminate()


def _tasa_nativa(indice):
    import pyaudio

    pa = pyaudio.PyAudio()
    try:
        info = pa.get_device_info_by_index(indice)
        return int(info.get("defaultSampleRate", 0)) or None
    except Exception:
        return None
    finally:
        pa.terminate()


def _capturar_audio(sr, listener, indice, timeout, phrase_time_limit):
    # SpeechRecognition abre a 16000 Hz por defecto. Micros USB baratos
    # (como el JV610) a veces rechazan esa tasa con "Unable to install hw
    # params", asi que si falla reintentamos con la tasa nativa del equipo.
    tasas = [None]
    nativa = _tasa_nativa(indice)
    if nativa and nativa != 16000:
        tasas.append(nativa)

    ultimo_error = None
    for tasa in tasas:
        try:
            mic = sr.Microphone(device_index=indice) if tasa is None \
                else sr.Microphone(device_index=indice, sample_rate=tasa)
            with mic as source:
                listener.adjust_for_ambient_noise(source, duration=1)
                return listener.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            raise
        except Exception as e:
            ultimo_error = e

    raise ultimo_error if ultimo_error else RuntimeError("No se pudo abrir el microfono.")


def _listen_worker(device_index, timeout, phrase_time_limit, language, queue):
    # Corre en un PROCESO separado a proposito: si PortAudio/ALSA hace
    # segmentation fault al abrir el microfono, solo muere este proceso
    # hijo. El proceso principal (main.py) nunca se entera y sigue vivo.
    import speech_recognition as sr

    try:
        indice = _resolve_input_device(device_index)
        if indice is None:
            queue.put(("error", "No se encontro ningun dispositivo de entrada de audio."))
            return

        listener = sr.Recognizer()
        listener.pause_threshold = 2.0
        listener.non_speaking_duration = 1.0
        listener.phrase_threshold = 0.2
        listener.dynamic_energy_threshold = True

        audio = _capturar_audio(sr, listener, indice, timeout, phrase_time_limit)
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

        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()

    async def texto_a_audio(self, text, output_path):
        import edge_tts

        communicate = edge_tts.Communicate(text=text, voice=self.voice_name, rate=self.voice_rate)
        await communicate.save(output_path)

    def talk(self, text):
        if not text:
            return

        import pygame

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

        # "spawn" en vez del "fork" por defecto de Linux: fork copia la
        # memoria del padre pero solo el hilo que llama. Como listen() se
        # invoca desde un hilo mientras pygame/ALSA tienen locks tomados en
        # otro, el hijo puede nacer bloqueado con un lock que nadie va a
        # liberar. spawn arranca un interprete limpio, sin locks heredados.
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        proc = ctx.Process(
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
