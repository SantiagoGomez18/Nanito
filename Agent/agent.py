from langchain_core.tools import tool
from langchain_core.messages import BaseMessage
import os
import getpass
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
import tools.spotifyTool as sp
from langgraph.checkpoint.memory import MemorySaver


class MessagesState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


SYSTEM_PROMPT = """Eres Nanito, un asistente de voz amable, claro y honesto.

Ayuda al usuario respondiendo preguntas y usando herramientas cuando haga falta.

Reglas:
- Si puedes hacer algo, hazlo.
- Si no puedes, si falla una herramienta o si no se puede confirmar el resultado, dilo claramente.
- No inventes resultados ni digas que algo se completo si la herramienta no lo confirmo.
- Responde breve, natural y sin markdown.
- No uses ** ni formato decorativo, porque la voz lo lee literal.

Para Spotify:
- Si el usuario menciona cancion y artista, llama la herramienta spotify separando song y artist.
- Si solo menciona la cancion, usa song y deja artist vacio.
- No inventes artista.
- Si la herramienta devuelve una coincidencia aproximada, dilo tal cual.
- Solo di que se esta reproduciendo si la herramienta lo confirmo."""


load_dotenv()


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("OPENAI_API_KEY")


@tool
def spotify(song: str, artist: str = "") -> str:
    """Reproduce en Spotify la cancion indicada por el usuario. Si conoces el artista, envialo por separado."""
    spotify_tool = sp.SpotifyTool()
    spotify_tool.authenticate()
    return spotify_tool.reproducir_cancion(song, artist)


tools = [
    spotify
]

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
llm_tool = llm.bind_tools(tools)
sys_msg = SystemMessage(content=SYSTEM_PROMPT)


def assistant(state: MessagesState):
    return {"messages": [llm_tool.invoke([sys_msg] + state["messages"])]}


def build_agent():
    builder = StateGraph(MessagesState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)
