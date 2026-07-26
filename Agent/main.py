import os
import time
import queue
import threading

# Debe ir ANTES de importar pygame. Con "spawn", el proceso hijo re-importa
# este modulo en cada escucha, asi que sin esto el banner de pygame se
# repetiria en cada ciclo.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")

import pygame
from langchain_core.messages import HumanMessage
from agent import build_agent
from tools.voiceTool import VoiceTool
from display.face import FaceDisplay


def extract_response_text(content):
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "").strip()
                if text:
                    parts.append(text)
            elif isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
        return " ".join(parts)

    return str(content)


def worker(graph, voice, face_queue):
    config = {"configurable": {"thread_id": "usuario_1"}}
    palabras_despedida = ["adios", "hasta luego", "chao", "nos vemos", "a dios", "adiós", "hasta pronto", "me voy", "me retiro", "me despido", "me desconecto"]
    palabras_despierta = ["nanito", "manito", "panito", "nanit", "anito"]
    tiempo_activo = 30
    modo_activo = False
    ultimo_comando = 0.0

    print("Nanito: Hola! En que puedo ayudarte hoy?")
    face_queue.put("neutral")
    voice.talk("Hola, soy Nanito. Estoy listo.")
    face_queue.put("neutral")

    while True:
        if not modo_activo:
            face_queue.put("sleep")
            wake_input = voice.listen(show_status=True, show_errors=True)

            wake_input_lower = wake_input.lower() if wake_input else ""
            palabra_encontrada = next((p for p in palabras_despierta if p in wake_input_lower), None)

            if not palabra_encontrada:
                continue

            user_input = wake_input_lower.replace(palabra_encontrada, "", 1).strip(" ,.")
            modo_activo = True
            ultimo_comando = time.time()

            if not user_input:
                face_queue.put("listen")
                voice.talk("Te escucho.")
                user_input = voice.listen(show_status=True, show_errors=False)
                if not user_input:
                    modo_activo = False
                    continue
        else:
            if time.time() - ultimo_comando > tiempo_activo:
                modo_activo = False
                continue

            face_queue.put("listen")
            user_input = voice.listen(show_status=True, show_errors=False)
            if not user_input:
                if time.time() - ultimo_comando > tiempo_activo:
                    modo_activo = False
                continue

        print(f"Usuario: {user_input}")

        for palabra in palabras_despedida:
            if palabra in user_input.lower():
                modo_activo = False
                continue

        face_queue.put("think")
        result = graph.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config
        )

        ultimo_comando = time.time()
        response = extract_response_text(result["messages"][-1].content)
        print("Nanito:", response)
        if response:
            face_queue.put("talk")
            voice.talk(response)
            face_queue.put("happy")


def main():
    graph = build_agent()
    voice = VoiceTool()
    face = FaceDisplay()
    face_queue = queue.Queue()

    threading.Thread(target=worker, args=(graph, voice, face_queue), daemon=True).start()

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        try:
            expression = face_queue.get_nowait()
            face.show(expression)
        except queue.Empty:
            pass

        face.render()
        clock.tick(30)


if __name__ == "__main__":
    main()
