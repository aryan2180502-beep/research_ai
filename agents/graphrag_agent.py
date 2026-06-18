# agents/graphrag_agent.py

import json
import logging
from typing import Annotated, Optional
from pydantic import BaseModel, Field
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from config import NVIDIA_MODEL, NVIDIA_API_KEY
from pipeline.pdf_parser import PDFParser
from graph.connection import Neo4jConnection
from pipeline.neo4j_ingestor import Neo4jIngestor

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 🧱 STEP 1: UNIFIED PYDANTIC SCHEMA
# ─────────────────────────────────────────────

class Relationship(BaseModel):
    """A single directed relationship between two concepts."""
    concept_a: str = Field(description="The source concept")
    concept_b: str = Field(description="The target concept")
    relation: str = Field(description="How concept_a relates to concept_b, e.g. 'improves', 'uses', 'extends'")

class PaperAnalysis(BaseModel):
    """
    Complete analysis of a research paper in ONE LLM call.
    Replaces ConceptList + RelationshipList.
    """
    concepts: list[str] = Field(
        description="5 to 8 key concepts from the paper as short noun phrases"
    )
    relationships: list[Relationship] = Field(
        description="Meaningful connections between the concepts"
    )

# ─────────────────────────────────────────────
# 🧱 STEP 2: LAZY NEO4J INIT (unchanged pattern)
# ─────────────────────────────────────────────

_neo4j_conn: Optional[Neo4jConnection] = None
_ingestor: Optional[Neo4jIngestor] = None

def get_ingestor() -> Neo4jIngestor:
    global _neo4j_conn, _ingestor
    if _ingestor is None:
        _neo4j_conn = Neo4jConnection()
        _neo4j_conn.connect()
        _ingestor = Neo4jIngestor(_neo4j_conn)
        logger.info("Neo4j ingestor initialized")
    return _ingestor

# ─────────────────────────────────────────────
# 🧱 STEP 3: UNIFIED TOOL (1 call instead of 2)
# ─────────────────────────────────────────────

@tool
def analyze_paper(pdf_path: str, paper_id: str) -> str:
    """
    Extracts concepts AND relationships from a PDF in a single LLM call.
    Stores results in Neo4j. Returns a summary string.
    """
    # --- Parse PDF text ---
    parser = PDFParser(max_pages=5)
    text = parser.extract_text(pdf_path)

    if not text:
        return json.dumps({"error": f"Could not extract text from {pdf_path}"})

    # --- One LLM call with structured output ---
    llm = ChatNVIDIA(
        model=NVIDIA_MODEL,
        api_key=NVIDIA_API_KEY,
        temperature=0,
    )
    structured_llm = llm.with_structured_output(PaperAnalysis)

    prompt = f"""You are a research paper analyzer. Extract information from this research paper.

Return ONLY these two things:
1. concepts: a list of 5 to 8 key concepts from the paper as short noun phrases
2. relationships: a list of connections between those concepts

Paper excerpt:
{text[:2500]}
"""
    result = None
    try:
        result = structured_llm.invoke(prompt)
    except Exception as e:
        logger.warning(f"Structured output call failed for {paper_id}: {e}")


    if result is None:
        logger.warning(f"Got None for {paper_id}, retrying with simpler prompt...")
        simple_prompt = f"""List 5 key concepts from this text as JSON.
Text: {text[:1500]}
Return only: {{"concepts": ["concept1", "concept2", ...], "relationships": []}}"""
        try:
            result = structured_llm.invoke(simple_prompt)
        except Exception as e:
            logger.error(f"Retry also failed for {paper_id}: {e}")

     # --- Layer 3: If still None, return safe error (don't crash) ---
    if result is None:
        logger.error(f"Could not extract structured output for paper {paper_id}")
        return json.dumps({
            "error": f"Structured output returned None for {paper_id}",
            "paper_id": paper_id,
        })

    # --- Write to Neo4j ---
    ingestor = get_ingestor()
    for concept in result.concepts:
        ingestor.add_concept_to_paper(paper_id, concept)

    for rel in result.relationships:
        ingestor.link_related_concepts(rel.concept_a, rel.concept_b)

    logger.info(
        f"Paper {paper_id}: stored {len(result.concepts)} concepts, "
        f"{len(result.relationships)} relationships"
    )

    return json.dumps({
        "paper_id": paper_id,
        "concepts": result.concepts,
        "relationships": [r.model_dump() for r in result.relationships],
    })


@tool
def get_graph_statistics() -> str:
    """Returns current Neo4j graph stats."""
    ingestor = get_ingestor()
    stats = ingestor.get_graph_stats()
    return json.dumps(stats)


# ─────────────────────────────────────────────
# 🧱 STEP 4: LANGGRAPH STATE + AGENT (unchanged pattern)
# ─────────────────────────────────────────────

class GraphRAGAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    papers: list[dict]   # [{paper_id, title, local_pdf_path}]

# ─────────────────────────────────────────────
# 🧱 STEP 5: PUBLIC RUNNER FUNCTION -- no langgraph
# ─────────────────────────────────────────────

def run_graphrag_agent(papers: list[dict]) -> dict:
    """
    Entry point called by orchestrator.
    Loops over papers and calls analyze_paper tool directly.
    No LangGraph needed — the workflow is deterministic, not agentic.
    """
    if not papers:
        return {"status": "no_papers", "processed": 0}

    results = []
    errors = []

    for paper in papers:
        paper_id = paper.get("paper_id")
        pdf_path = paper.get("local_pdf_path")

        # Skip papers with no PDF
        if not pdf_path:
            logger.warning(f"Skipping {paper_id} — no local_pdf_path")
            continue

        logger.info(f"Processing paper: {paper_id}")
        try:
            # Call the tool function directly (not via LangGraph)
            output = analyze_paper.invoke({
                "pdf_path": pdf_path,
                "paper_id": paper_id,
            })
            parsed = json.loads(output)

            if "error" in parsed:
                logger.warning(f"Paper {paper_id} returned error: {parsed['error']}")
                errors.append(parsed["error"])
            else:
                results.append(parsed)
                logger.info(
                    f"✅ {paper_id}: "
                    f"{len(parsed.get('concepts', []))} concepts, "
                    f"{len(parsed.get('relationships', []))} relationships"
                )

        except Exception as e:
            msg = f"Failed to process {paper_id}: {e}"
            logger.error(msg)
            errors.append(msg)

    return {
        "status": "complete",
        "processed": len(results),
        "errors": errors,
        "papers": results,
    }