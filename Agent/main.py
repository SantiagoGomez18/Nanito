import time
from langchain_core.messages import HumanMessage
from agent import build_agent
from tools.voiceTool import VoiceTool


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


def main():
    graph = build_agent()
    voice = VoiceTool()

    config = {
        "configurable": {
            "thread_id": "usuario_1"
        }
    }

    palabras_despedida = ["adios", "hasta luego", "chao", "nos vemos", "a dios"]
    palabra_despierta = "nanito"
    tiempo_activo = 40
    modo_activo = False
    ultimo_comando = 0.0

    print("Nanito: Hola! En que puedo ayudarte hoy?")
    voice.talk("Hola, soy Nanito. Estoy listo.")

    while True:
        if not modo_activo:
            wake_input = voice.listen(show_status=False, show_errors=False)

            if not wake_input or palabra_despierta not in wake_input.lower():
                continue

            user_input = wake_input.replace(palabra_despierta, "", 1).strip(" ,.")
            modo_activo = True
            ultimo_comando = time.time()

            if not user_input:
                voice.talk("Te escucho.")
                user_input = voice.listen(show_status=True, show_errors=False)
                if not user_input:
                    modo_activo = False
                    continue
        else:
            if time.time() - ultimo_comando > tiempo_activo:
                modo_activo = False
                continue

            user_input = voice.listen(show_status=True, show_errors=False)
            if not user_input:
                if time.time() - ultimo_comando > tiempo_activo:
                    modo_activo = False
                continue

        print(f"Usuario: {user_input}")

        for palabra in palabras_despedida:
            if palabra in user_input.lower():
                print("Nanito: Hasta luego!")
                voice.talk("Hasta luego")
                return

        result = graph.invoke(
            {
                "messages": [
                    HumanMessage(content=user_input)
                ]
            },
            config=config
        )

        ultimo_comando = time.time()
        response = extract_response_text(result["messages"][-1].content)
        print("Nanito:", response)
        if response:
            voice.talk(response)


if __name__ == "__main__":
    main()
