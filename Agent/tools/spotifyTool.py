from spotipy.oauth2 import SpotifyOAuth
import spotipy
import os
import random
import re
import unicodedata
from dotenv import load_dotenv

load_dotenv()

MAX_COLA = 30  # limite maximo total de canciones en la cola
CANCIONES_POR_PEDIDO = 15  # cuantas canciones nuevas se agregan al pedir una cancion

class SpotifyTool:
    def __init__(self):
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI')
        self.song = ""
        self.author = ""
        self.flag = 0
        self.sp = None
        self.cola = []  # cola interna gestionada: lista de tracks (dicts de Spotify)
        self.scope = "user-modify-playback-state user-read-playback-state playlist-read-private playlist-read-collaborative user-library-read"

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
            open_browser=False,
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

        if not exact_match and not artist_name:
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
        candidatos = self._buscar_candidatos(found_artist, track["id"])
        self._reconstruir_cola(track, candidatos, device_id)

        return f"Reproduciendo {track_name} de {found_artist} en {device_name}"

    def agregar_cancion(self, song, artist=""):
        song_name = song.strip()
        artist_name = artist.strip()

        track, _, exact_match = self.buscar_cancion(song_name, artist_name)
        if not track:
            return "No encontre esa cancion en Spotify."

        track_name = track["name"]
        found_artist = track["artists"][0]["name"]

        if not exact_match and not artist_name:
            return f'No encontre coincidencia exacta. La mas relevante fue "{track_name}" de {found_artist}.'

        if any(t["id"] == track["id"] for t in self.cola):
            return f"{track_name} ya esta en la cola."

        devices = self.sp.devices().get("devices", [])
        if not devices:
            return "No encontre dispositivos activos de Spotify. Abre Spotify y vuelve a intentarlo."

        active_device = next((d for d in devices if d.get("is_active")), None)
        selected_device = active_device if active_device else devices[0]
        device_id = selected_device["id"]

        # Leer la cancion y posicion actual para reanudarla casi sin corte.
        current_uri = None
        current_id = None
        position_ms = 0
        try:
            current = self.sp.current_playback()
            if current and current.get("item"):
                current_uri = current["item"]["uri"]
                current_id = current["item"]["id"]
                position_ms = current.get("progress_ms", 0)
        except Exception as e:
            print(f"No se pudo leer la reproduccion actual: {e}")

        # La nueva cancion va al frente de la cola gestionada (suena a continuacion).
        cola_sin_actual = [t for t in self.cola if t["id"] != current_id]
        self.cola = ([track] + cola_sin_actual)[:MAX_COLA]

        try:
            self.sp.shuffle(False, device_id=device_id)
        except Exception as e:
            print(f"No se pudo apagar el modo aleatorio: {e}")

        try:
            if current_uri:
                uris = [current_uri] + [t["uri"] for t in self.cola]
                self.sp.start_playback(device_id=device_id, uris=uris, position_ms=position_ms)
            else:
                uris = [t["uri"] for t in self.cola]
                self.sp.start_playback(device_id=device_id, uris=uris)
        except Exception as e:
            print(f"No se pudo reconstruir la cola: {e}")
            return "No pude agregar la cancion a la cola."

        return f"{track_name} de {found_artist} sonara a continuacion."

    def _reconstruir_cola(self, track_actual, candidatos, device_id):
        # Mezcla los candidatos nuevos con la cola previa, sin duplicar
        # canciones, mezcla todo y respeta el limite maximo.
        random.shuffle(candidatos)
        candidatos = candidatos[:CANCIONES_POR_PEDIDO]  # cuantas nuevas por pedido
        combinados = self.cola + candidatos

        ids_vistos = {track_actual["id"]}
        cola_unica = []
        for t in combinados:
            if t["id"] in ids_vistos:
                continue
            ids_vistos.add(t["id"])
            cola_unica.append(t)

        random.shuffle(cola_unica)
        self.cola = cola_unica[:MAX_COLA]

        # Apagar shuffle para que la cancion pedida suene primero.
        try:
            self.sp.shuffle(False, device_id=device_id)
        except Exception as e:
            print(f"No se pudo apagar el modo aleatorio: {e}")

        # Todo va por CONTEXTO (un solo start_playback con la lista completa),
        # nunca add_to_queue. Asi "agregar" puede insertar al frente despues.
        # Con shuffle apagado, la cancion pedida suena primero (uris[0]).
        uris = [track_actual["uri"]] + [t["uri"] for t in self.cola]
        self.sp.start_playback(device_id=device_id, uris=uris)
        print(f"Cola: {len(self.cola)} canciones (max {MAX_COLA}).")

    def _buscar_candidatos(self, artist_name, track_id):
        # La app tiene cap de limit bajo: usamos limit=5 y paginamos con offset.
        vistos = {track_id}
        candidatos = []
        for offset in range(0, 45, 5):
            try:
                resultado = self.sp.search(
                    q=f'artist:"{artist_name}"', type="track", limit=5, offset=offset
                )
                items = resultado.get("tracks", {}).get("items", [])
            except Exception as e:
                print(f"Fallo busqueda (offset {offset}): {e}")
                break

            if not items:
                break

            for t in items:
                if t["id"] not in vistos:
                    vistos.add(t["id"])
                    candidatos.append(t)

        print(f"Candidatos encontrados: {len(candidatos)}")
        return candidatos
    
    def _es_me_gusta(self, nombre):
        n = self.normalizar_texto(nombre)
        claves = ["tus me gusta", "me gusta", "mis likes", "mis me gusta", "likes", "favoritos", "canciones que me gustan"]
        return any(clave in n for clave in claves)

    def reproducir_me_gusta(self, aleatorio=False):
        # Las canciones con "me gusta" no tienen URI de playlist, se reproducen por lista de tracks.
        uris = []
        offset = 0
        while len(uris) < 50:
            try:
                resultado = self.sp.current_user_saved_tracks(limit=5, offset=offset)
            except Exception as e:
                print(f"Fallo al leer canciones guardadas: {e}")
                break
            items = resultado.get("items", [])
            if not items:
                break
            for item in items:
                track = item.get("track")
                if track:
                    uris.append(track["uri"])
            if len(items) < 5:
                break
            offset += 5

        if not uris:
            return "No tienes canciones guardadas en me gusta."

        if aleatorio:
            random.shuffle(uris)

        devices = self.sp.devices().get("devices", [])
        if not devices:
            return "No encontre dispositivos activos de Spotify. Abre Spotify y vuelve a intentarlo."

        active_device = next((d for d in devices if d.get("is_active")), None)
        selected_device = active_device if active_device else devices[0]
        device_id = selected_device["id"]
        device_name = selected_device["name"]

        self.cola = []  # la cola gestionada se descarta al poner me gusta
        self.sp.start_playback(device_id=device_id, uris=uris)
        modo = " en modo aleatorio" if aleatorio else ""
        return f"Reproduciendo tus canciones que te gustan{modo} en {device_name}"

    def reproducir_playlist(self, nombre, aleatorio=False):
        if self._es_me_gusta(nombre):
            return self.reproducir_me_gusta(aleatorio)

        playlist = self._buscar_playlist(nombre)
        if not playlist:
            return f"No encontre una playlist llamada {nombre}."

        devices = self.sp.devices().get("devices", [])
        if not devices:
            return "No encontre dispositivos activos de Spotify. Abre Spotify y vuelve a intentarlo."

        active_device = next((d for d in devices if d.get("is_active")), None)
        selected_device = active_device if active_device else devices[0]
        device_id = selected_device["id"]
        device_name = selected_device["name"]

        try:
            self.sp.shuffle(aleatorio, device_id=device_id)
        except Exception as e:
            print(f"No se pudo cambiar el modo aleatorio: {e}")

        self.cola = []  # la cola gestionada se descarta al poner una playlist
        self.sp.start_playback(device_id=device_id, context_uri=playlist["uri"])
        modo = " en modo aleatorio" if aleatorio else ""
        return f"Reproduciendo la playlist {playlist['name']}{modo} en {device_name}"

    def _buscar_playlist(self, nombre):
        objetivo = self.normalizar_texto(nombre)
        mejor_parcial = None
        offset = 0
        while True:
            try:
                resultado = self.sp.current_user_playlists(limit=5, offset=offset)
            except Exception as e:
                print(f"Fallo al listar playlists: {e}")
                break

            items = resultado.get("items", [])
            if not items:
                break

            for pl in items:
                if not pl:
                    continue
                nombre_pl = self.normalizar_texto(pl["name"])
                if nombre_pl == objetivo:
                    return pl
                if mejor_parcial is None and (objetivo in nombre_pl or nombre_pl in objetivo):
                    mejor_parcial = pl

            if len(items) < 5:
                break
            offset += 5

        return mejor_parcial

    def frenar_cancion(self):
        self.sp.pause_playback()

    def continuar_cancion(self):
        try:
            self.sp.start_playback()
            return "Reproduccion reanudada."
        except Exception as e:
            print(f"No se pudo reanudar: {e}")
            return "No hay nada que reanudar."