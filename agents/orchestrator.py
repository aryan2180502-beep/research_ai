# agents/orchestrator.py

import logging
from dataclasses import dataclass, field
from datetime import datetime

from agents.arxiv_agent import run_arxiv_agent
from agents.graphrag_agent import run_graphrag_agent
from graph.connection import Neo4jConnection
from graph.queries import (
    get_graph_summary,
    find_research_gaps,
    get_most_connected_concepts,
)
from agents.websearch_agent import run_websearch_agent
from agents.critic_agent import run_critic_agent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 🧱 STEP 1: RESULT DATACLASS
# ─────────────────────────────────────────────

@dataclass
class OrchestrationResult:
    """Structured result returned after a full pipeline run."""
    query: str
    papers_found: int = 0
    papers_analyzed: int = 0
    graph_summary: dict = field(default_factory=dict)
    research_gaps: list[dict] = field(default_factory=list)
    hub_concepts: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    web_findings: list[dict] = field(default_factory=list)
    web_summary: str = ""
    critique: dict = field(default_factory=dict)

    def to_report(self) -> str:
        """Renders the result as a human-readable markdown report."""
        gaps = "\n".join(
            f"  - {g['concept']} (in {g['paper_count']} papers)"
            for g in self.research_gaps
        ) or "  None found yet — add more papers."

        hubs = "\n".join(
            f"  - {h['concept']} ({h['connections']} connections)"
            for h in self.hub_concepts
        ) or "  No hub concepts yet."

        errors = "\n".join(f"  - {e}" for e in self.errors) or "  None"

        return f"""# ResearchPilot Report
**Query:** {self.query}
**Run:** {self.started_at} → {self.completed_at}

## Pipeline Summary
- Papers found:    {self.papers_found}
- Papers analyzed: {self.papers_analyzed}
- Total papers in graph:        {self.graph_summary.get('papers', 0)}
- Total concepts in graph:      {self.graph_summary.get('concepts', 0)}
- Total relationships in graph: {self.graph_summary.get('relationships', 0)}

## Research Gaps (isolated concepts)
{gaps}

## Hub Concepts (most connected)
{hubs}

## Errors
{errors}

## Web Search Findings
{self._format_web_findings()}

## 🔍 Report Critique
{self._format_critique()}
"""

    def _format_web_findings(self) -> str:
        """Formats web findings for the markdown report."""
        if not self.web_findings:
            return "  No web findings available."

        lines = [self.web_summary, ""]
        for i, finding in enumerate(self.web_findings, 1):
            lines.append(f"### Finding {i}: {finding['title']}")
            lines.append(finding['summary'])
            lines.append(f"*Relevance:* {finding['relevance']}")
            lines.append(f"*Source:* {finding['source_url']}")
            lines.append("")
        return "\n".join(lines)
    


    
    def _format_critique(self) -> str:
        """Formats critique scores for the markdown report."""
        if not self.critique or self.critique.get("status") == "error":
            return "  Critique unavailable."

        lines = [
            f"**Overall Score: {self.critique['overall_score']}/100"
            f" — {self.critique['verdict'].upper()}**\n",
        ]
        for dim, data in self.critique.get("dimensions", {}).items():
            lines.append(
                f"- **{dim.replace('_', ' ').title()}:**"
                f" {data['score']}/10 — {data['reasoning']}"
            )

        lines.append("\n**Strengths:**")
        for s in self.critique.get("strengths", []):
            lines.append(f"- {s}")

        lines.append("\n**Weaknesses:**")
        for w in self.critique.get("weaknesses", []):
            lines.append(f"- {w}")

        lines.append(
            f"\n**Recommendation:** {self.critique.get('recommendation', '')}"
        )
        return "\n".join(lines)
# ─────────────────────────────────────────────
# 🧱 STEP 2: ORCHESTRATOR CLASS
# ─────────────────────────────────────────────

class Orchestrator:
    """
    Coordinates the ArXiv agent and GraphRAG agent.
    Runs the full pipeline for a given research query.
    """

    def __init__(self, max_papers: int = 3):
        self.max_papers = max_papers
        logger.info(f"Orchestrator initialized (max_papers={max_papers})")

    def run(self, query: str) -> OrchestrationResult:
        result = OrchestrationResult(
            query=query,
            started_at=datetime.now().isoformat(timespec="seconds"),
        )

        # ── STAGE 1: ArXiv Agent ──────────────────────────
        logger.info(f"[Stage 1] ArXiv agent starting for query: '{query}'")
        try:
            arxiv_result = run_arxiv_agent(query)
            papers = arxiv_result.get("papers", [])
            result.papers_found = len(papers)
            logger.info(f"[Stage 1] Found {len(papers)} papers")
        except Exception as e:
            msg = f"ArXiv agent failed: {e}"
            logger.error(msg)
            result.errors.append(msg)
            papers = []

        # ── STAGE 2: GraphRAG Agent ───────────────────────
        if papers:
            logger.info(f"[Stage 2] GraphRAG agent analyzing {len(papers)} papers")
            try:
                graphrag_result = run_graphrag_agent(papers[: self.max_papers])
                result.papers_analyzed = graphrag_result.get("processed", 0)
                logger.info(f"[Stage 2] Analyzed {result.papers_analyzed} papers")
            except Exception as e:
                msg = f"GraphRAG agent failed: {e}"
                logger.error(msg)
                result.errors.append(msg)
        else:
            logger.warning("[Stage 2] Skipped — no papers from Stage 1")
            

        # ── Stage 2.5: Web Search ─────────────────────────────────────────────   
        logger.info("Stage 2.5: Running web search agent")
        try:
            web_result = run_websearch_agent(query, max_results=5)

            if web_result["status"] in ("success", "partial"):
                result.web_findings = web_result["findings"]
                result.web_summary = web_result["overall_summary"]
                logger.info(f"Web search complete: {len(result.web_findings)} findings")
            else:
                result.errors.append(f"Web search failed: {web_result['errors']}")
                logger.warning("Web search returned error status — continuing pipeline")

        except Exception as e:
            # Same try/except pattern as every other stage —
            # one agent failing never stops the pipeline
            result.errors.append(f"Web search stage exception: {e}")
            logger.error(f"Web search stage crashed: {e}")

        # ── STAGE 3: Graph Queries ────────────────────────
        logger.info("[Stage 3] Running graph queries")
        try:
            conn = Neo4jConnection()
            conn.connect()
            result.graph_summary = get_graph_summary(conn)
            result.research_gaps = find_research_gaps(conn, min_papers=1)
            result.hub_concepts = get_most_connected_concepts(conn, top_n=5)
            conn.close()
        except Exception as e:
            msg = f"Graph queries failed: {e}"
            logger.error(msg)
            result.errors.append(msg)

        # ── STAGE 4: Critic Agent ─────────────────────────
        logger.info("[Stage 4] Critic agent evaluating report")
        try:
            partial_report = self._build_partial_report(result)
            critique_result = run_critic_agent(query, partial_report)
            result.critique = critique_result
            logger.info(
                f"[Stage 4] Critique complete — "
                f"Score: {critique_result.get('overall_score', 'N/A')}/100 "
                f"| Verdict: {critique_result.get('verdict', 'N/A')}"
            )
        except Exception as e:
            msg = f"Critic agent failed: {e}"
            logger.error(msg)
            result.errors.append(msg)

        result.completed_at = datetime.now().isoformat(timespec="seconds")
        logger.info("[Orchestrator] Pipeline complete")
        return result

    def _build_partial_report(self, result: OrchestrationResult) -> str:
        """
        Builds a report string to pass to the critic.
        We can't call result.to_report() here — critique isn't set yet,
        and to_report() calls _format_critique() which would return empty.
        This gives the critic all the meaningful content without recursion.
        """
        gaps = ", ".join(
            g["concept"] for g in result.research_gaps
        ) or "none identified"

        hubs = ", ".join(
            h["concept"] for h in result.hub_concepts
        ) or "none identified"

        findings = "\n".join(
            f"- {f['title']}: {f['summary']}"
            for f in result.web_findings
        ) or "none"

        return (
            f"Query: {result.query}\n\n"
            f"Papers found: {result.papers_found}\n"
            f"Papers analyzed: {result.papers_analyzed}\n"
            f"Total concepts in graph: {result.graph_summary.get('concepts', 0)}\n"
            f"Total relationships: {result.graph_summary.get('relationships', 0)}\n\n"
            f"Research gaps identified: {gaps}\n"
            f"Hub concepts: {hubs}\n\n"
            f"Web findings:\n{findings}\n"
            f"Web summary: {result.web_summary}\n"
        )


# ─────────────────────────────────────────────
# 🧱 STEP 3: CONVENIENCE RUNNER
# ─────────────────────────────────────────────

def run_pipeline(query: str, max_papers: int = 3) -> str:
    """
    Top-level entry point. Returns a markdown report string.
    Called by main.py, FastAPI routes, and Gradio UI later.
    """
    orchestrator = Orchestrator(max_papers=max_papers)
    result = orchestrator.run(query)
    return result.to_report()