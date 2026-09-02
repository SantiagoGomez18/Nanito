"""Diagnostico de Spotify, aislado del agente.

Verifica cuenta, mercado, dispositivos y reproduccion de UNA cancion,
mostrando exactamente que responde la API en cada paso.

Uso:  python Agent/test_spotify.py
"""
import sys
import time

import tools.spotifyTool as sp


def main():
    tool = sp.SpotifyTool()
    tool.authenticate()
    s = tool.sp

    print("=" * 55)
    print("1) CUENTA")
    try:
        u = s.current_user()
        producto = u.get("product")
        pais = u.get("country")
        print(f"   usuario : {u.get('display_name')} ({u.get('id')})")
        print(f"   pais    : {pais}")
        print(f"   producto: {producto}")

        if producto is None or pais is None:
            print("   >>> El token NO trae 'product'/'country'.")
            print("       Falta el scope user-read-private.")
            print("       Borra .spotify_cache y volve a autenticar.")
            return 1
        if producto == "free":
            print("   >>> Cuenta gratuita: la API no puede controlar la reproduccion.")
            return 1
    except Exception as e:
        print(f"   ERROR: {e}")
        return 1

    print("\n2) DISPOSITIVOS")
    try:
        devs = s.devices().get("devices", [])
        if not devs:
            print("   >>> NO HAY DISPOSITIVOS. Abre Spotify y dale play a algo.")
            return 1
        for d in devs:
            print(f"   - {d.get('name')} | tipo={d.get('type')} | "
                  f"activo={d.get('is_active')} | privado={d.get('is_private_session')} "
                  f"| restringido={d.get('is_restricted')} | vol={d.get('volume_percent')}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return 1

    print("\n3) ESTADO ACTUAL")
    try:
        est = s.current_playback()
        if not est:
            print("   sin sesion activa (Spotify no esta reproduciendo nada)")
        else:
            it = est.get("item") or {}
            print(f"   is_playing={est.get('is_playing')} | sonando={it.get('name')}")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n4) BUSQUEDA (con market del usuario)")
    market = tool._mercado()
    print(f"   market usado: {market}")
    try:
        res = s.search(q='track:"BAILE INoLVIDABLE" artist:"Bad Bunny"',
                       type="track", limit=1, market=market)
        items = res.get("tracks", {}).get("items", [])
        if not items:
            print("   >>> la busqueda no devolvio nada")
            return 1
        t = items[0]
        print(f"   encontrada : {t['name']} - {t['artists'][0]['name']}")
        print(f"   uri        : {t['uri']}")
        print(f"   is_playable: {t.get('is_playable')}")
        if t.get("restrictions"):
            print(f"   restricciones: {t['restrictions']}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return 1

    activo = next((d for d in devs if d.get("is_active")), None)
    destino = activo if activo else devs[0]
    print(f"\n5) REPRODUCIR en '{destino.get('name')}'")
    try:
        s.start_playback(device_id=destino["id"], uris=[t["uri"]])
        print("   start_playback: aceptado (204, sin excepcion)")
    except Exception as e:
        print(f"   start_playback FALLO: {e}")
        return 1

    print("\n6) COMPROBACION (3 s)")
    for i in range(3):
        time.sleep(1)
        try:
            est = s.current_playback()
        except Exception as e:
            print(f"   ERROR: {e}")
            break
        if est:
            it = est.get("item") or {}
            print(f"   t+{i+1}s  is_playing={est.get('is_playing')} | "
                  f"sonando={it.get('name')}")
            if est.get("is_playing") and it.get("id") == t["id"]:
                print("\n>>> FUNCIONO. El problema no es Spotify ni la cuenta.")
                return 0
        else:
            print(f"   t+{i+1}s  sin sesion activa")

    print("\n>>> NO ARRANCO con una sola cancion y el dispositivo activo.")
    print("    El cliente de Spotify no esta respondiendo a Connect.")
    print("    Cierra Spotify por completo en la laptop, abrilo de nuevo,")
    print("    dale play a cualquier cancion, y volve a correr este test.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
