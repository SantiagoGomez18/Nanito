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


def _conf(nombre, defecto):
    try:
        return float(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def _capturar_audio(sr, listener, indice, timeout, phrase_time_limit):
    # SpeechRecognition abre a 16000 Hz por defecto. Micros USB baratos
    # (como el JV610) a veces rechazan esa tasa con "Unable to install hw
    # params", asi que si falla reintentamos con la tasa nativa del equipo.
    tasas = [None]
    nativa = _tasa_nativa(indice)
    if nativa and nativa != 16000:
        tasas.append(nativa)

    # Duracion del muestreo de ruido ambiente. Con el ventilador de la Pi
    # cerca del microfono, este ajuste sube el umbral y termina ignorando
    # la voz. NANITO_AJUSTE_RUIDO=0 lo desactiva por completo.
    ajuste = _conf("NANITO_AJUSTE_RUIDO", 1.0)

    ultimo_error = None
    for tasa in tasas:
        try:
            mic = sr.Microphone(device_index=indice) if tasa is None \
                else sr.Microphone(device_index=indice, sample_rate=tasa)
            with mic as source:
                if ajuste > 0:
                    listener.adjust_for_ambient_noise(source, duration=ajuste)
                if os.environ.get("NANITO_MIC_INFO") == "1":
                    print(f"[mic] umbral de energia: {listener.energy_threshold:.0f}")
                return listener.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            raise
        except Exception as e:
            ultimo_error = e

    raise ultimo_error if ultimo_error else RuntimeError("No se pudo abrir el microfono.")


def _silenciar_stderr():
    # ALSA, JACK y PortAudio escriben sus avisos directo al descriptor 2
    # desde codigo C, asi que un try/except de Python no los intercepta:
    # hay que redirigir el descriptor. Perder stderr aca no nos deja ciegos
    # porque los errores reales del worker viajan por el Pipe, no por stderr.
    # Con NANITO_DEBUG=1 se conserva la salida para diagnosticar.
    if os.environ.get("NANITO_DEBUG") == "1":
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)
    except Exception:
        pass


def _responder(conn, estado, dato):
    try:
        conn.send((estado, dato))
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _listen_worker(device_index, timeout, phrase_time_limit, language, conn):
    # Corre en un PROCESO separado a proposito: si PortAudio/ALSA hace
    # segmentation fault al abrir el microfono, solo muere este proceso
    # hijo. El proceso principal (main.py) nunca se entera y sigue vivo.
    _silenciar_stderr()
    import speech_recognition as sr

    try:
        indice = _resolve_input_device(device_index)
        if indice is None:
            _responder(conn, "error", "No se encontro ningun dispositivo de entrada de audio.")
            return

        listener = sr.Recognizer()
        listener.pause_threshold = _conf("NANITO_PAUSA", 2.0)
        listener.non_speaking_duration = min(1.0, listener.pause_threshold)
        listener.phrase_threshold = _conf("NANITO_FRASE_MIN", 0.2)

        # Si se fija NANITO_ENERGIA, se usa ese umbral y se desactiva el
        # ajuste automatico: es la forma directa de hacer el mic mas
        # sensible cuando el ruido de fondo enganaba al calculo dinamico.
        energia = os.environ.get("NANITO_ENERGIA")
        if energia:
            try:
                listener.energy_threshold = float(energia)
                listener.dynamic_energy_threshold = False
            except ValueError:
                listener.dynamic_energy_threshold = True
        else:
            listener.dynamic_energy_threshold = True

        audio = _capturar_audio(sr, listener, indice, timeout, phrase_time_limit)
        rec = listener.recognize_google(audio, language=language)
        _responder(conn, "ok", rec.lower())
    except sr.WaitTimeoutError:
        _responder(conn, "timeout", None)
    except sr.UnknownValueError:
        _responder(conn, "unknown", None)
    except sr.RequestError as e:
        _responder(conn, "request_error", str(e))
    except Exception as e:
        _responder(conn, "error", str(e))


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

        # Pipe en vez de Queue: cada Queue reserva 3 semaforos del sistema y,
        # como se creaba una por escucha, el resource_tracker avisaba de
        # "leaked semaphore objects". Solo necesitamos devolver un valor.
        recv_conn, send_conn = ctx.Pipe(duplex=False)
        proc = ctx.Process(
            target=_listen_worker,
            args=(self.device_index, self.timeout, self.phrase_time_limit, self.language, send_conn),
            daemon=True
        )
        try:
            return self._ejecutar_escucha(proc, recv_conn, send_conn, show_status, show_errors)
        finally:
            for c in (recv_conn, send_conn):
                try:
                    c.close()
                except Exception:
                    pass

    def _ejecutar_escucha(self, proc, recv_conn, send_conn, show_status, show_errors):
        proc.start()
        # El padre cierra su copia del extremo de escritura: asi, si el hijo
        # muere sin responder, el pipe queda cerrado y poll() no se cuelga.
        try:
            send_conn.close()
        except Exception:
            pass
        proc.join(timeout=self.timeout + 15)

        if proc.is_alive():
            # terminate() manda SIGTERM, que un proceso trabado dentro de una
            # lectura ALSA no llega a atender: quedaba vivo reteniendo el
            # microfono y rompia la corrida siguiente ("Subdevices: 0/1").
            # Por eso escalamos a SIGKILL, que no se puede ignorar.
            proc.terminate()
            proc.join(timeout=3)

            if proc.is_alive():
                proc.kill()
                proc.join(timeout=3)

            if show_errors:
                estado = "no se pudo matar" if proc.is_alive() else "proceso terminado"
                print(f"El microfono no respondio a tiempo ({estado}), se omite este intento.")
            return ""

        if proc.exitcode != 0:
            if show_errors:
                print(f"El proceso de escucha fallo (codigo {proc.exitcode}), se omite este intento.")
            return ""

        try:
            if not recv_conn.poll(0):
                return ""
            status, data = recv_conn.recv()
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
