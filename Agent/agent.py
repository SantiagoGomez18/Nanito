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
import tools.alarmTool as al
from langgraph.checkpoint.memory import MemorySaver
import threading


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
- Para alarmas:
- Usa poner_alarma para duraciones relativas como "en 10 minutos".
- Usa poner_alarma_hora para horas exactas como "a las 6:55".

Para Spotify:
- Si el usuario menciona cancion y artista, llama la herramienta spotify separando song y artist.
- Si solo menciona la cancion, usa song y deja artist vacio.
- No inventes artista.
- Si el usuario pide una playlist o lista, usa spotify_poner_playlist con el nombre.
- Si pide modo aleatorio, shuffle o desordenado, pon aleatorio en True.
- Si el usuario menciona la lista de reproduccion "mis likes" o "me gusta", se refiere a la lista "Tus me gusta" .
- Si el usuario dice pausar o frenar, usa spotify_frenar_cancion.
- Si el usuario dice continua, reanuda o sigue la cancion, usa spotify_continuar_cancion.
- Si la herramienta devuelve una coincidencia aproximada, dilo tal cual.
- Solo di que se esta reproduciendo si la herramienta lo confirmo."""

load_dotenv()

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("OPENAI_API_KEY")

# Crea las instancias de las herramientas una vez para evitar problemas de inicialización múltiple
spotifyTool = sp.SpotifyTool()
alarmTool = al.AlarmTool()

# tools
@tool
def spotify_poner_cancion(song: str, artist: str = "") -> str:
    """Reproduce en Spotify la cancion indicada por el usuario. Si conoces el artista, envialo por separado."""
    spotifyTool.authenticate()
    return spotifyTool.reproducir_cancion(song, artist)

@tool
def spotify_poner_playlist(nombre: str, aleatorio: bool = False) -> str:
    """Reproduce una playlist del usuario en Spotify por su nombre. Pon aleatorio en True si el usuario pide modo aleatorio o shuffle."""
    spotifyTool.authenticate()
    return spotifyTool.reproducir_playlist(nombre, aleatorio)

@tool
def spotify_frenar_cancion() -> str:
    """Detiene la cancion que se esta reproduciendo en Spotify."""
    spotifyTool.authenticate()
    spotifyTool.frenar_cancion()
    return "Cancion detenida."

@tool
def spotify_continuar_cancion() -> str:
    """Reanuda la reproduccion que estaba pausada en Spotify."""
    spotifyTool.authenticate()
    return spotifyTool.continuar_cancion()

@tool
def poner_alarma(seconds: int = 0, minutes: int = 0, hour: int = 0) -> str:
    """Configura una alarma que sonara despues del tiempo indicado."""
    creada = alarmTool.start_alarm(seconds, minutes, hour)
    if not creada:
        return "No pude configurar la alarma porque el tiempo indicado no es valido."
    return "Alarma configurada."

@tool
def poner_alarma_hora(hour: int, minutes: int = 0, period: str = "") -> str:
    """Configura una alarma para una hora exacta. period puede ser am, pm o vacio."""
    creada = alarmTool.alarm_at(hour, minutes, period)
    if not creada:
        return "No pude configurar la alarma para esa hora."
    return "Alarma configurada."

@tool
def detener_alarma() -> str:
    """Detiene la alarma si esta sonando."""
    alarmTool.stop_alarm()
    return "Alarma detenida."

@tool
def snooze_alarma(minutes: int) -> str:
    """Pospone la alarma por el tiempo indicado."""
    alarmTool.stop_alarm()
    alarmTool.start_alarm(minutes=minutes)
    return f"Alarma pospuesta por {minutes} minutos."

tools = [
    spotify_poner_cancion,
    spotify_poner_playlist,
    spotify_frenar_cancion,
    spotify_continuar_cancion,
    poner_alarma,
    poner_alarma_hora,
    detener_alarma,
    snooze_alarma
]

# Configuracion del agente
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
llm_tool = llm.bind_tools(tools)
sys_msg = SystemMessage(content=SYSTEM_PROMPT)


def assistant(state: MessagesState):
    return {"messages": [llm_tool.invoke([sys_msg] + state["messages"])]}

# Construccion del grafo
def build_agent():
    builder = StateGraph(MessagesState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)
