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

    primeraVez = True
    palabras_despedida = ["adios", "hasta luego", "chao", "nos vemos", "a dios", "adiós"]

    print("Hola, soy Nanito! ¿En qué puedo ayudarte hoy?")
    voice.talk("Hola, soy Nanito! ¿En qué puedo ayudarte hoy?")

    while True:
        
        if primeraVez:
            voice.talk("Te escucho.")
            primeraVez = False
            
        user_input = voice.listen()
        if user_input:
            print(f"Usuario: {user_input}")

        if not user_input:
            print("Nanito: No escuche nada.")
            voice.talk("No escuche nada.")
            continue

        for palabra in palabras_despedida:
            if palabra in user_input.lower():
                print("Nanito: ¡Hasta luego!")
                voice.talk("¡Hasta luego!")
                return

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
