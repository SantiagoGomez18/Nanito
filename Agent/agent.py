from langchain_core.tools import tool
from langchain_core.messages import BaseMessage
import os
import getpass
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
import tools.spotifyTool as sp
from langgraph.checkpoint.memory import MemorySaver


class MessagesState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


SYSTEM_PROMPT = """Eres un asistente de inteligencia artificial llamado Nanito, tus tareas principales son:
                    - Responder preguntas de los usuarios.
                    - Realizar tareas utilizando las herramientas a tu disposicion."""


load_dotenv()


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("GEMINI_API_KEY")


@tool
def spotify(song: str) -> str:
    """Reproduce en Spotify la cancion indicada por el usuario."""
    spotify_tool = sp.SpotifyTool()
    spotify_tool.authenticate()
    return spotify_tool.reproducir_cancion(song)


tools = [
    spotify
]

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
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
