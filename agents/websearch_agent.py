# agents/websearch_agent.py

import logging
from typing import Optional
from pydantic import BaseModel, Field
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_tavily import TavilySearch
import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# SECTION 1: Pydantic Output Schema
# ─────────────────────────────────────────

class WebFinding(BaseModel):
    """Represents one meaningful finding extracted from web search results."""
    title: str = Field(description="Title or headline of the finding")
    summary: str = Field(description="2-3 sentence summary of what was found")
    relevance: str = Field(description="Why this is relevant to the research query")
    source_url: str = Field(description="URL where this was found")


class WebSearchAnalysis(BaseModel):
    """Structured output from the LLM after analyzing web search results."""
    findings: list[WebFinding] = Field(
        description="List of key findings from the web search"
    )
    overall_summary: str = Field(
        description="One paragraph synthesizing all findings"
    )
    gaps_identified: list[str] = Field(
        description="Research gaps or open questions surfaced by web results"
    )


# ─────────────────────────────────────────
# SECTION 2: Tavily Search Tool
# ─────────────────────────────────────────

def build_search_tool(max_results: int = 5):
    """
    Creates a configured Tavily search tool.
    max_results controls how many web pages come back.
    """
    return TavilySearch(
        max_results=max_results,
        search_depth="advanced",       # deeper crawl vs "basic"
        include_answer=True,           # Tavily's own summary on top
        include_raw_content=False,     # skip raw HTML — we want clean text
        include_images=False,
    )


# ─────────────────────────────────────────
# SECTION 3: Core Analysis Function
# ─────────────────────────────────────────

def analyze_web_results(
    query: str,
    raw_results: list[dict],
    llm_with_schema
) -> Optional[WebSearchAnalysis]:
    """
    Sends raw Tavily results to the LLM and extracts structured findings.
    Has the same three-layer defense pattern as graphrag_agent's analyze_paper().
    """

    # Format raw results into readable text for the LLM
    formatted = ""
    for i, result in enumerate(raw_results, 1):
        formatted += f"\n[Result {i}]\n"
        formatted += f"URL: {result.get('url', 'N/A')}\n"
        formatted += f"Content: {result.get('content', '')[:800]}\n"  # cap at 800 chars

    prompt = f"""You are a research analyst. Analyze these web search results about: "{query}"

Search Results:
{formatted}

Extract the most important findings. Be specific and factual."""

    # Layer 1: Primary attempt
    try:
        analysis = llm_with_schema.invoke(prompt)
        if analysis is not None:
            return analysis
        logger.warning("LLM returned None on first attempt — retrying with simpler prompt")
    except Exception as e:
        logger.warning(f"Primary LLM call failed: {e}")

    # Layer 2: Simpler retry prompt
    try:
        simple_prompt = f"""Research topic: "{query}"

Web results summary: {formatted[:1000]}

List 2-3 key findings and a brief overall summary."""
        analysis = llm_with_schema.invoke(simple_prompt)
        if analysis is not None:
            return analysis
    except Exception as e:
        logger.warning(f"Retry LLM call also failed: {e}")

    # Layer 3: Safe error return — never crash the pipeline
    logger.error(f"Both LLM attempts failed for query: {query}")
    return None


# ─────────────────────────────────────────
# SECTION 4: Main Agent Function
# ─────────────────────────────────────────

def run_websearch_agent(
    query: str,
    max_results: int = 5
) -> dict:
    """
    Main entry point. Orchestrator calls this exactly like run_arxiv_agent().

    Returns:
    {
        "query": str,
        "status": "success" | "partial" | "error",
        "findings": list[dict],
        "overall_summary": str,
        "gaps_identified": list[str],
        "raw_result_count": int,
        "errors": list[str]
    }
    """
    logger.info(f"WebSearch Agent starting for query: '{query}'")
    errors = []

    # ── Step 1: Initialize LLM with structured output schema ──
    try:
        llm = ChatNVIDIA(
            model=config.NVIDIA_MODEL,
            api_key=config.NVIDIA_API_KEY,
            temperature=0,             # deterministic output
        )
        llm_with_schema = llm.with_structured_output(WebSearchAnalysis)
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return _error_return(query, f"LLM init failed: {e}")

    # ── Step 2: Run Tavily Search ──
    try:
        search_tool = build_search_tool(max_results=max_results)
        logger.info(f"Searching web for: '{query}'")
        raw_response = search_tool.invoke(query)        # returns a dict now
        raw_results = raw_response.get("results", [])   # actual results are nested here
        logger.info(f"Tavily returned {len(raw_results)} results")
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return _error_return(query, f"Web search failed: {e}")

    if not raw_results:
        return _error_return(query, "Tavily returned zero results")

    # ── Step 3: LLM Analysis of results ──
    analysis = analyze_web_results(query, raw_results, llm_with_schema)

    if analysis is None:
        errors.append("LLM analysis failed — returning raw results only")
        return {
            "query": query,
            "status": "partial",
            "findings": _raw_to_findings(raw_results),
            "overall_summary": "LLM analysis unavailable.",
            "gaps_identified": [],
            "raw_result_count": len(raw_results),
            "errors": errors,
        }

    # ── Step 4: Package and return ──
    logger.info(f"WebSearch Agent complete. {len(analysis.findings)} findings extracted.")
    return {
        "query": query,
        "status": "success",
        "findings": [f.model_dump() for f in analysis.findings],
        "overall_summary": analysis.overall_summary,
        "gaps_identified": analysis.gaps_identified,
        "raw_result_count": len(raw_results),
        "errors": errors,
    }


# ─────────────────────────────────────────
# SECTION 5: Helper Functions
# ─────────────────────────────────────────

def _error_return(query: str, reason: str) -> dict:
    """Consistent error shape — orchestrator can always rely on these keys existing."""
    logger.error(f"WebSearch Agent error: {reason}")
    return {
        "query": query,
        "status": "error",
        "findings": [],
        "overall_summary": "",
        "gaps_identified": [],
        "raw_result_count": 0,
        "errors": [reason],
    }


def _raw_to_findings(raw_results: list[dict]) -> list[dict]:
    """
    Fallback when LLM fails — converts raw Tavily results into
    the same shape as WebFinding so the orchestrator gets consistent data.
    """
    findings = []
    for r in raw_results:
        findings.append({
            "title": r.get("title", "Untitled"),
            "summary": r.get("content", "")[:300],
            "relevance": "Relevance analysis unavailable",
            "source_url": r.get("url", ""),
        })
    return findings