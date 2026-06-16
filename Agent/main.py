from langchain_core.messages import HumanMessage
from agent import build_agent


def main():

    graph = build_agent()

    config = {
        "configurable": {
            "thread_id": "usuario_1"
        }
    }

    print("Nanito: ¿En qué puedo ayudarte hoy?")

    while True:
        user_input = input("Usuario: ")
        
        if user_input.lower() in ["salir", "exit", "quit"]:
            print("Nanito: ¡Hasta luego!")
            break

        result = graph.invoke(
            {
                "messages": [
                    HumanMessage(content=user_input)
                ]
            },
            config=config
        )

        print(
            "Nanito:",
            result["messages"][-1].content
        )


if __name__ == "__main__":
    main()