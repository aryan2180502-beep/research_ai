# agents/arxiv_agent.py
#
# An autonomous agent that searches ArXiv and downloads papers.
# Uses LangGraph to manage the agent loop and LangChain tools
# to give the LLM the ability to search and download.

import logging
from typing import Annotated, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from config import NVIDIA_MODEL, NVIDIA_API_KEY
from pipeline.arxiv_fetcher import ArXivFetcher, Paper

import warnings
warnings.filterwarnings("ignore", message="Key '.*' is not supported in schema")

logger = logging.getLogger(__name__)

# ── Shared fetcher instance ───────────────────────────────────────────
# Created once here, used by all tools below.
# This is the same singleton pattern from Neo4jConnection.
_fetcher = ArXivFetcher()


# ── Tools ─────────────────────────────────────────────────────────────
# Tools are just Python functions with the @tool decorator.
# The decorator does two things:
# 1. Tells LangChain this function is callable by the LLM
# 2. Uses the docstring to explain to the LLM what the tool does
#    (the LLM reads the docstring to decide when to use it)

@tool
def search_arxiv(query: str, max_results: int = 5) -> str:
    """
    Search ArXiv for research papers matching a query.
    Returns a summary of papers found including titles and IDs.
    Use this first to find relevant papers before downloading.
    """
    papers = _fetcher.search_papers(query, max_results)

    if not papers:
        return "No papers found for this query."

    # Format results as readable text for the LLM
    lines = [f"Found {len(papers)} papers:\n"]
    for i, paper in enumerate(papers, 1):
        lines.append(f"{i}. [{paper.paper_id}] {paper.title}")
        lines.append(f"   Authors: {', '.join(paper.authors[:3])}")
        # [:3] shows max 3 authors — papers can have 20+ authors
        lines.append(f"   Published: {paper.published}")
        lines.append(f"   Abstract: {paper.abstract[:200]}...")
        lines.append("")

    return "\n".join(lines)


@tool
def fetch_and_download_papers(query: str, max_results: int = 3) -> str:
    """
    Search ArXiv AND download the PDFs to local storage.
    Use this when you want to fully retrieve papers for analysis.
    Returns the paper IDs and local file paths of downloaded papers.
    """
    papers = _fetcher.fetch_and_download(query, max_results)

    if not papers:
        return "No papers were downloaded successfully."

    lines = [f"Successfully downloaded {len(papers)} papers:\n"]
    for paper in papers:
        lines.append(f"- {paper.paper_id}: {paper.title[:60]}")
        lines.append(f"  Path: {paper.local_pdf_path}")

    return "\n".join(lines)


# ── Agent State ───────────────────────────────────────────────────────
class ArXivAgentState(TypedDict):
    """
    The shared memory of the ArXiv agent.

    TypedDict is like a regular dict but with type hints —
    it tells Python (and you) exactly what keys exist and
    what type each value is.

    Every node in the graph reads from and writes to this state.
    Think of it as the agent's working memory for one task.
    """
    messages: Annotated[list, add_messages]
    # messages: the conversation history between user and agent
    # Annotated[list, add_messages] is LangGraph magic:
    # instead of replacing the list each time, add_messages
    # APPENDS new messages to the existing list.
    # This is how the agent remembers what it has done so far.

    query: str
    # The original search query — stored so we never lose it

    papers_found: List[dict]
    # Papers the agent has found, stored as dicts for serialization


# ── LLM Setup ─────────────────────────────────────────────────────────
def _create_llm_with_tools():
    """
    Creates the Gemini LLM and binds our tools to it.

    'Binding' tools means telling the LLM:
    'These functions exist. You can call them by name.
     Here is what each one does (from its docstring).'

    After binding, the LLM can respond with either:
    - A text message (thinking/final answer)
    - A tool call (I want to run search_arxiv with these args)
    """
    llm = ChatNVIDIA(
        model=NVIDIA_MODEL,
        api_key=NVIDIA_API_KEY,
        temperature=0
        # temperature=0 means deterministic output —
        # same input always gives same output.
        # Good for agents where consistency matters.
        # Higher temperature = more creative/random.
    )

    tools = [search_arxiv, fetch_and_download_papers]
    return llm.bind_tools(tools)


# ── Graph Nodes ───────────────────────────────────────────────────────
# A node is one step in the agent's workflow.
# Each node is a function that takes state and returns updated state.

def agent_node(state: ArXivAgentState) -> dict:
    """
    The 'thinking' node — calls the LLM to decide what to do next.

    The LLM looks at the messages so far and either:
    1. Calls a tool (search_arxiv or fetch_and_download_papers)
    2. Gives a final text answer (done)
    """
    llm_with_tools = _create_llm_with_tools()

    # System message tells the LLM its role and behaviour
    system = SystemMessage(content="""
    You are a research paper discovery agent specializing in finding
    academic papers on ArXiv.

    When given a research topic:
    1. First use search_arxiv to find relevant papers
    2. Then use fetch_and_download_papers to download the most relevant ones
    3. Finally, summarize what you found

    Always download at least 2-3 papers for thorough research coverage.
    """)

    # Prepend system message to conversation history
    messages = [system] + state["messages"]

    response = llm_with_tools.invoke(messages)
    # invoke() sends messages to Gemini and gets a response back.
    # The response is either text or a tool call instruction.

    return {"messages": [response]}
    # Return just the new message — add_messages will append it
    # to the existing messages list in state automatically.


def should_continue(state: ArXivAgentState) -> str:
    """
    The router — decides what happens after the agent thinks.

    This is called an 'edge function' in LangGraph.
    It looks at the last message and returns a string
    that tells LangGraph which node to go to next.

    Returns "tools" → run the tool the LLM requested
    Returns "end"   → agent is done, stop the graph
    """
    last_message = state["messages"][-1]
    # [-1] gets the last item in the list — the most recent message

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # tool_calls is set when the LLM wants to call a tool
        # If it exists and is not empty → go run the tool
        return "tools"

    return "end"
    # No tool calls in the last message → LLM gave a final answer


# ── Build the Graph ───────────────────────────────────────────────────
def create_arxiv_agent():
    """
    Assembles the LangGraph agent and returns a runnable app.

    The graph structure:
    START → agent → [tools → agent] loop → END

    The agent and tools keep passing control back and forth
    until the agent decides it's done (no more tool calls).
    """
    # ToolNode automatically runs whatever tool the LLM requested
    tools = [search_arxiv, fetch_and_download_papers]
    tool_node = ToolNode(tools)
    # ToolNode is a prebuilt LangGraph node that:
    # 1. Reads the tool_calls from the last message
    # 2. Finds the matching function
    # 3. Calls it with the provided arguments
    # 4. Returns the result as a ToolMessage

    # Create the graph with our state type
    graph = StateGraph(ArXivAgentState)

    # Add nodes (the steps)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # Add edges (the wiring)
    graph.add_edge(START, "agent")
    # Always start at the agent node

    graph.add_conditional_edges(
        "agent",           # from this node...
        should_continue,   # call this function to decide...
        {
            "tools": "tools",   # if it returns "tools" → go to tools node
            "end": END          # if it returns "end" → stop
        }
    )
    # Conditional edges = the LLM controls what happens next

    graph.add_edge("tools", "agent")
    # After running a tool → always go back to agent to think again

    return graph.compile()
    # compile() finalizes the graph and returns a runnable object


# ── Public Interface ──────────────────────────────────────────────────
def run_arxiv_agent(query: str) -> dict:
    """
    The main function other parts of the system call.

    query: research topic to search for
    Returns: dict with the agent's findings
    """
    logger.info(f"🤖 ArXiv Agent starting for query: '{query}'")

    app = create_arxiv_agent()

    # Initial state — this is what the agent starts with
    initial_state = {
        "messages": [HumanMessage(content=f"Find research papers about: {query}")],
        "query": query,
        "papers_found": []
    }

    # Run the graph until it reaches END
    final_state = app.invoke(initial_state)

    # Extract the last message (agent's final answer)
    final_message = final_state["messages"][-1].content

    logger.info("✅ ArXiv Agent complete")

    return {
        "query": query,
        "summary": final_message,
        "message_count": len(final_state["messages"])
        # message_count tells you how many back-and-forth
        # steps the agent took — useful for debugging
    }