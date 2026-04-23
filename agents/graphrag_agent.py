# agents/graphrag_agent.py

import json
import logging
import warnings
from typing import Annotated, List

warnings.filterwarnings("ignore", message="Key '.*' is not supported in schema")

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from config import GOOGLE_API_KEY
from graph.connection import Neo4jConnection
from pipeline.neo4j_ingestor import Neo4jIngestor
from pipeline.pdf_parser import PDFParser

logger = logging.getLogger(__name__)


# ── Pydantic Schemas ──────────────────────────────────────────────────
# These define the EXACT shape the LLM must return.
# No free text, no markdown, no guessing.

class ConceptList(BaseModel):
    """Schema for concept extraction."""
    concepts: list[str] = Field(
        description="Technical concepts, methods, and topics from the paper. Maximum 15."
    )

class ConceptPair(BaseModel):
    """One pair of related concepts."""
    concept_a: str
    concept_b: str

class RelationshipList(BaseModel):
    """Schema for relationship extraction."""
    pairs: list[ConceptPair] = Field(
        description="Pairs of concepts that are meaningfully related. Maximum 10."
    )


# ── Module-level instances ────────────────────────────────────────────
_parser = PDFParser(max_pages=5)
_conn = None
_ingestor = None

def _get_ingestor() -> Neo4jIngestor:
    """Lazy initialization — only connects to Neo4j when first needed."""
    global _conn, _ingestor
    if _ingestor is None:
        _conn = Neo4jConnection()
        _ingestor = Neo4jIngestor(_conn)
    return _ingestor

def _create_llm():
    """Creates a fresh Gemini LLM instance."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-lite-001",
        google_api_key=GOOGLE_API_KEY,
        temperature=0
    )


# ── Tools ─────────────────────────────────────────────────────────────

@tool
def extract_concepts_from_pdf(pdf_path: str, paper_id: str) -> str:
    """
    Extract key concepts from a research paper PDF using AI.
    Reads the PDF text and identifies the main technical concepts,
    methods, and topics discussed in the paper.
    Returns a JSON list of concept names.
    """
    # Step 1: Extract text from PDF
    text = _parser.extract_text(pdf_path)
    if not text:
        return json.dumps({"error": f"Could not extract text from {pdf_path}"})

    # Step 2: Call LLM with structured output — guaranteed ConceptList back
    structured_llm = _create_llm().with_structured_output(ConceptList)

    prompt = f"""
    Read this research paper text and extract the key technical concepts.

    Focus on:
    - Methods and algorithms (e.g. "attention mechanism", "BERT", "FAISS")
    - Research areas (e.g. "natural language processing", "drug discovery")
    - Technical components (e.g. "vector embeddings", "knowledge graph")
    - Evaluation metrics (e.g. "BLEU score", "F1 score")

    Be specific, not generic.
    Bad: ["machine learning", "data", "model"]
    Good: ["retrieval augmented generation", "dense passage retrieval", "FAISS"]

    Paper text:
    {text[:3000]}
    """

    result = structured_llm.invoke(prompt)
    # result is a ConceptList object — result.concepts is always list[str]
    # No JSON parsing, no markdown stripping, no try/except needed here

    # Step 3: Store concepts in Neo4j
    ingestor = _get_ingestor()
    for concept in result.concepts:
        if concept.strip():
            ingestor.add_concept_to_paper(paper_id, concept.strip())

    logger.info(f"✅ Extracted {len(result.concepts)} concepts from {paper_id}")

    return json.dumps({
        "paper_id": paper_id,
        "concepts": result.concepts,
        "count": len(result.concepts)
    })


@tool
def extract_relationships_from_concepts(paper_id: str, concepts_json: str) -> str:
    """
    Given a list of concepts from a paper, identify which concepts
    are related to each other and store those relationships in the graph.
    concepts_json should be a JSON array of concept name strings.
    """
    try:
        concepts = json.loads(concepts_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON in concepts_json"})

    if len(concepts) < 2:
        return json.dumps({"message": "Need at least 2 concepts to find relationships"})

    # Call LLM with structured output — guaranteed RelationshipList back
    structured_llm = _create_llm().with_structured_output(RelationshipList)

    prompt = f"""
    Given these technical concepts from a research paper, identify which
    pairs of concepts are meaningfully related to each other.

    Concepts: {json.dumps(concepts)}

    Only include pairs with a genuine technical relationship.
    Maximum 10 pairs.
    """

    result = structured_llm.invoke(prompt)
    # result is a RelationshipList object
    # result.pairs is always a list of ConceptPair objects
    # each ConceptPair has .concept_a and .concept_b — always strings

    ingestor = _get_ingestor()
    for pair in result.pairs:
        ingestor.link_related_concepts(pair.concept_a, pair.concept_b)

    logger.info(f"✅ Stored {len(result.pairs)} relationships for {paper_id}")

    return json.dumps({
        "paper_id": paper_id,
        "relationships_stored": len(result.pairs),
        "pairs": [[p.concept_a, p.concept_b] for p in result.pairs]
    })


@tool
def get_graph_statistics() -> str:
    """
    Returns the current state of the knowledge graph —
    how many papers, authors, concepts, and relationships exist.
    Use this at the end to confirm data was stored correctly.
    """
    ingestor = _get_ingestor()
    stats = ingestor.get_graph_stats()
    return json.dumps(stats)


# ── Agent State ───────────────────────────────────────────────────────
class GraphRAGAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    papers: List[dict]


# ── Graph Nodes ───────────────────────────────────────────────────────
def agent_node(state: GraphRAGAgentState) -> dict:
    tools = [
        extract_concepts_from_pdf,
        extract_relationships_from_concepts,
        get_graph_statistics
    ]
    llm_with_tools = _create_llm().bind_tools(tools)

    system = SystemMessage(content="""
    You are a knowledge graph construction agent.
    Your job is to process research papers and build a knowledge graph.

    For each paper provided:
    1. Call extract_concepts_from_pdf with the pdf_path and paper_id
    2. Take the concepts returned and call extract_relationships_from_concepts
    3. After processing ALL papers, call get_graph_statistics once

    Process one paper at a time, completing both steps before moving to the next.
    """)

    messages = [system] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: GraphRAGAgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


# ── Build the Graph ───────────────────────────────────────────────────
def create_graphrag_agent():
    tools = [
        extract_concepts_from_pdf,
        extract_relationships_from_concepts,
        get_graph_statistics
    ]
    tool_node = ToolNode(tools)

    graph = StateGraph(GraphRAGAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


# ── Public Interface ──────────────────────────────────────────────────
def run_graphrag_agent(papers: list) -> dict:
    """
    Main function called by the Orchestrator.
    papers: list of dicts with keys paper_id, title, local_pdf_path
    """
    if not papers:
        return {"error": "No papers provided"}

    logger.info(f"🤖 GraphRAG Agent starting — processing {len(papers)} papers")

    app = create_graphrag_agent()

    papers_description = "\n".join([
        f"- paper_id: {p['paper_id']}, "
        f"title: {p['title'][:60]}, "
        f"pdf_path: {p['local_pdf_path']}"
        for p in papers
    ])

    initial_state = {
        "messages": [HumanMessage(
            content=f"Process these research papers into the knowledge graph:\n{papers_description}"
        )],
        "papers": papers
    }

    final_state = app.invoke(initial_state)
    final_message = final_state["messages"][-1].content

    logger.info("✅ GraphRAG Agent complete")

    return {
        "papers_processed": len(papers),
        "summary": final_message,
        "steps_taken": len(final_state["messages"])
    }