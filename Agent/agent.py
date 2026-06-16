from langchain_core.messages import BaseMessage
import os, getpass
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage
import spotifyTool as sp
from langgraph.checkpoint.memory import MemorySaver

# Definir el estado de los mensajes utilizando TypedDict
class MessagesState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
        
#System prompt
SYSTEM_PROMPT = """Eres un asistente de inteligencia artificial llamado Nanito, tus tareas principales son:
                    - Responder preguntas de los usuarios.
                    - Realizar tareas utilizando las herramientas a tu disposición."""

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Función para establecer variables de entorno si no están ya definidas
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("GEMINI_API_KEY")

# Configuración del modelo de lenguaje y herramientas
tools = [# sp.SpotifyTool()
        # weather.WeatherTool()
        # search.GoogleSearchTool()
        ]
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

llm_tool = llm.bind_tools(tools)

sys_msg = SystemMessage(content=SYSTEM_PROMPT)

# Definición de la función del asistente que procesa el estado de los mensajes y genera una respuesta utilizando el modelo de lenguaje y las herramientas disponibles
def assistant(state: MessagesState):
    return {"messages": [llm_tool.invoke([sys_msg] + state["messages"])]}


def build_agent():
    # Grafo
    builder = StateGraph(MessagesState)

    # Definicion de nodos
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))

    # Definir edges
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant",
        # If the latest message (result) from assistant is a tool call -> tools_condition routes to tools
        # If the latest message (result) from assistant is a not a tool call -> tools_condition routes to END
        tools_condition,
    )
    builder.add_edge("tools", "assistant")

    # Memoria
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)
    
