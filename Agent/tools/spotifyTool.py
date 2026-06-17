from spotipy.oauth2 import SpotifyOAuth
import spotipy
import os
import re
import unicodedata
from dotenv import load_dotenv

load_dotenv()


class SpotifyTool:
    def __init__(self):
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI')
        self.song = ""
        self.author = ""
        self.flag = 0
        self.sp = None
        self.scope = "user-modify-playback-state user-read-playback-state"

    def normalizar_texto(self, text):
        text = text.lower().strip()
        text = unicodedata.normalize("NFD", text)
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        return re.sub(r"\s+", " ", text)

    def es_exacto(self, requested_song, requested_artist, found_song, found_artist):
        same_song = self.normalizar_texto(requested_song) == self.normalizar_texto(found_song)

        if requested_artist:
            same_artist = self.normalizar_texto(requested_artist) == self.normalizar_texto(found_artist)
            return same_song and same_artist

        return same_song

    def buscar_cancion(self, song_name, artist_name=""):
        queries = []

        if artist_name:
            queries.append(f'track:"{song_name}" artist:"{artist_name}"')
            queries.append(f"{song_name} {artist_name}")

        queries.append(song_name)

        for query in queries:
            result = self.sp.search(q=query, type="track", limit=5)
            tracks = result.get("tracks", {}).get("items", [])
            if not tracks:
                continue

            for track in tracks:
                found_song = track["name"]
                found_artist = track["artists"][0]["name"]
                if self.es_exacto(song_name, artist_name, found_song, found_artist):
                    return track, query, True

            return tracks[0], query, False

        return None, queries[0], False

    def authenticate(self):
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("Spotify Client ID, Client Secret and Redirect URI must be set in environment variables.")

        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            open_browser=True,
            cache_path=".spotify_cache"
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

    def reproducir_cancion(self, song, artist=""):
        if self.flag != 0:
            return "No se pudo reproducir la cancion."

        song_name = song.strip()
        artist_name = artist.strip()
        self.song = song_name.upper()
        self.author = artist_name.upper() if artist_name else ""

        if artist_name:
            print(f"Buscando: {self.song} - {self.author}")
        else:
            print(f"Buscando: {self.song}")

        track, used_query, exact_match = self.buscar_cancion(song_name, artist_name)
        print(f"Consulta usada: {used_query}")

        if not track:
            print("No se encontraron canciones con ese nombre.")
            return "No encontre esa cancion en Spotify."

        track_name = track["name"]
        found_artist = track["artists"][0]["name"]
        track_uri = track["uri"]

        print(f"Encontrada: {track_name} - {found_artist}")

        if not exact_match:
            return f'No encontre coincidencia exacta. La mas relevante fue "{track_name}" de {found_artist}.'

        devices = self.sp.devices().get("devices", [])
        if not devices:
            print("No hay dispositivos activos de Spotify.")
            return "No encontre dispositivos activos de Spotify. Abre Spotify en tu celular o computador y vuelve a intentarlo."

        active_device = next((device for device in devices if device.get("is_active")), None)
        selected_device = active_device if active_device else devices[0]
        device_id = selected_device["id"]
        device_name = selected_device["name"]

        print(f"Reproduciendo en: {device_name}")
        self.sp.start_playback(device_id=device_id, uris=[track_uri])
        return f"Reproduciendo {track_name} de {found_artist} en {device_name}"
    