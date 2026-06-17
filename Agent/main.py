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

    print("Nanito: En que puedo ayudarte hoy?")
    voice.talk("En que puedo ayudarte hoy?")

    while True:
        voice.talk("Te escucho.")
        user_input = voice.listen()
        if user_input:
            print(f"Usuario: {user_input}")

        if not user_input:
            print("Nanito: No escuche nada.")
            voice.talk("No escuche nada.")
            continue

        if user_input.lower() in ["salir", "exit", "quit", "adios", "hasta luego"]:
            print("Nanito: Hasta luego!")
            voice.talk("Hasta luego")
            break

        result = graph.invoke(
            {
                "messages": [
                    HumanMessage(content=user_input)
                ]
            },
            config=config
        )

        response = extract_response_text(result["messages"][-1].content)
        print("Nanito:", response)
        if response:
            voice.talk(response)


if __name__ == "__main__":
    main()
