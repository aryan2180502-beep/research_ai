# agents/critic_agent.py

import logging
from typing import Optional
from pydantic import BaseModel, Field
from langchain_nvidia_ai_endpoints import ChatNVIDIA
import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# SECTION 1: Pydantic Output Schemas
# ─────────────────────────────────────────

class DimensionScore(BaseModel):
    """Score for a single evaluation dimension."""
    score: int = Field(
        description="Score from 0 to 10",
        ge=0,   # ge = greater than or equal to
        le=10,  # le = less than or equal to
    )
    reasoning: str = Field(
        description="One sentence explaining this score"
    )


class CritiqueResult(BaseModel):
    """Full structured critique of a research report."""

    relevance: DimensionScore = Field(
        description="How well the report addresses the original query"
    )
    coverage: DimensionScore = Field(
        description="Breadth of topics and sources covered"
    )
    evidence_quality: DimensionScore = Field(
        description="Quality and credibility of sources cited"
    )
    gap_identification: DimensionScore = Field(
        description="How well research gaps are identified and explained"
    )
    actionability: DimensionScore = Field(
        description="How useful this report is for a researcher to act on"
    )

    overall_score: int = Field(
        description="Overall score from 0 to 100",
        ge=0,
        le=100,
    )
    verdict: str = Field(
        description="One of: 'excellent', 'good', 'acceptable', 'needs_improvement'"
    )
    strengths: list[str] = Field(
        description="2-3 specific things the report does well"
    )
    weaknesses: list[str] = Field(
        description="2-3 specific things the report could improve"
    )
    recommendation: str = Field(
        description="One concrete suggestion to improve the report"
    )


# ─────────────────────────────────────────
# SECTION 2: Score → Verdict helper
# ─────────────────────────────────────────

def score_to_verdict(score: int) -> str:
    """
    Maps a 0-100 score to a human-readable verdict.
    Defined here so we can use it as a fallback if the LLM
    returns an unexpected verdict string.
    """
    if score >= 80:
        return "excellent"
    elif score >= 65:
        return "good"
    elif score >= 45:
        return "acceptable"
    else:
        return "needs_improvement"


# ─────────────────────────────────────────
# SECTION 3: Core Critique Function
# ─────────────────────────────────────────

def critique_report(
    query: str,
    report: str,
    llm_with_schema,
) -> Optional[CritiqueResult]:
    """
    Sends the report to the LLM and gets a structured critique back.
    Same three-layer defense pattern used throughout the project.
    """

    # Cap report length — long reports can confuse smaller models
    report_excerpt = report[:3000]

    prompt = f"""You are a senior research analyst and peer reviewer.

Evaluate this research report against the original query.

Original Query: "{query}"

Report:
{report_excerpt}

Score each dimension from 0-10 and provide an overall score from 0-100.
Be specific and critical — a perfect score should be rare."""

    # Layer 1: Primary attempt
    try:
        critique = llm_with_schema.invoke(prompt)
        if critique is not None:
            # Normalize verdict in case LLM returns unexpected string
            critique.verdict = score_to_verdict(critique.overall_score)
            return critique
        logger.warning("LLM returned None on first attempt — retrying")
    except Exception as e:
        logger.warning(f"Primary critique attempt failed: {e}")

    # Layer 2: Simpler retry
    try:
        simple_prompt = f"""Rate this research report about "{query}".

Report excerpt: {report_excerpt[:1500]}

Give scores 0-10 for: relevance, coverage, evidence_quality,
gap_identification, actionability.
Give an overall score 0-100.
List 2 strengths and 2 weaknesses."""

        critique = llm_with_schema.invoke(simple_prompt)
        if critique is not None:
            critique.verdict = score_to_verdict(critique.overall_score)
            return critique
    except Exception as e:
        logger.warning(f"Retry critique attempt failed: {e}")

    # Layer 3: Safe return
    logger.error(f"Both critique attempts failed for query: '{query}'")
    return None


# ─────────────────────────────────────────
# SECTION 4: Main Agent Function
# ─────────────────────────────────────────

def run_critic_agent(
    query: str,
    report: str,
) -> dict:
    """
    Main entry point. Orchestrator calls this with the finished report.

    Returns:
    {
        "status": "success" | "error",
        "overall_score": int,        # 0-100
        "verdict": str,              # excellent/good/acceptable/needs_improvement
        "dimensions": dict,          # per-dimension scores + reasoning
        "strengths": list[str],
        "weaknesses": list[str],
        "recommendation": str,
        "errors": list[str],
    }
    """
    logger.info(f"Critic Agent starting for query: '{query}'")

    # Guard: if report is empty, nothing to critique
    if not report or len(report.strip()) < 50:
        return _error_return(query, "Report is empty or too short to critique")

    # ── Initialize LLM ──
    try:
        llm = ChatNVIDIA(
            model=config.NVIDIA_MODEL,
            api_key=config.NVIDIA_API_KEY,
            temperature=0,
        )
        llm_with_schema = llm.with_structured_output(CritiqueResult)
    except Exception as e:
        return _error_return(query, f"LLM init failed: {e}")

    # ── Run critique ──
    critique = critique_report(query, report, llm_with_schema)

    if critique is None:
        return _error_return(query, "LLM critique returned None after retries")

    # ── Package dimensions into a clean dict ──
    dimensions = {
        "relevance":          {"score": critique.relevance.score,
                               "reasoning": critique.relevance.reasoning},
        "coverage":           {"score": critique.coverage.score,
                               "reasoning": critique.coverage.reasoning},
        "evidence_quality":   {"score": critique.evidence_quality.score,
                               "reasoning": critique.evidence_quality.reasoning},
        "gap_identification": {"score": critique.gap_identification.score,
                               "reasoning": critique.gap_identification.reasoning},
        "actionability":      {"score": critique.actionability.score,
                               "reasoning": critique.actionability.reasoning},
    }

    logger.info(
        f"Critic Agent complete. "
        f"Score: {critique.overall_score}/100 | Verdict: {critique.verdict}"
    )

    return {
        "status": "success",
        "overall_score": critique.overall_score,
        "verdict": critique.verdict,
        "dimensions": dimensions,
        "strengths": critique.strengths,
        "weaknesses": critique.weaknesses,
        "recommendation": critique.recommendation,
        "errors": [],
    }


# ─────────────────────────────────────────
# SECTION 5: Helper
# ─────────────────────────────────────────

def _error_return(query: str, reason: str) -> dict:
    """Consistent error shape so orchestrator always gets the same keys."""
    logger.error(f"Critic Agent error: {reason}")
    return {
        "status": "error",
        "overall_score": 0,
        "verdict": "needs_improvement",
        "dimensions": {},
        "strengths": [],
        "weaknesses": [],
        "recommendation": "Pipeline error — could not generate critique.",
        "errors": [reason],
    }