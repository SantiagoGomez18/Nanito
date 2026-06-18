Proyecto de Santiago Gomez Ordoñez. 
Github: SantiagoGomez18

# Nanito

Nanito es un asistente de voz en Python que escucha comandos, responde con voz y puede usar herramientas como Spotify y alarmas.

## Version de Python

Usa `Python 3.12`.

Se recomienda esa version porque fue la que funciono bien con las dependencias del proyecto, especialmente audio, `pygame`, `SpeechRecognition` y `PyAudio`.

## Crear entorno

Si usas conda:

```bash
conda create -n Nanito python=3.12 -y
conda activate Nanito
```

## Instalar dependencias

Desde la raiz del proyecto:

```bash
pip install -r requirements.txt
```

## Variables de entorno

Crea un archivo `.env` en la raiz del proyecto con estas variables:

```env
OPENAI_API_KEY=tu_api_key
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
SPOTIPY_REDIRECT_URI=tu_redirect_uri
```

## Ejecutar

```bash
python Agent/main.py
```

## Funciones actuales

- Activacion por voz con la palabra `nanito`
- Respuestas por voz usando `edge-tts`
- Reproduccion de canciones en Spotify
- Pausar canciones en Spotify
- Alarmas por tiempo relativo
- Alarmas por hora exacta
- Apagar alarma
- Posponer alarma

## Notas

- Spotify requiere autenticacion de usuario y un dispositivo activo.
- Para reproducir en Spotify normalmente necesitas cuenta Premium.
- La voz usa `edge-tts`, asi que requiere internet.
- El reconocimiento de voz actual tambien requiere internet.
- La alarma necesita un archivo de audio en:

```text
Agent/tools/audio/alarm.mp3
```

## Raspberry Pi

Para Raspberry Pi 4, ademas de `pip install -r requirements.txt`, probablemente necesites instalar paquetes del sistema para audio.

Ejemplo comun:

```bash
sudo apt update
sudo apt install -y portaudio19-dev python3-dev python3-pygame ffmpeg
```
