# api/routes.py
#
# FastAPI HTTP layer for ResearchPilot. Exposes the orchestrator
# pipeline, saved reports, and graph stats over HTTP so the Gradio
# UI (or any other client) doesn't need to import Python directly.

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.orchestrator import Orchestrator
from graph.connection import Neo4jConnection
from graph.queries import get_graph_summary

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "reports"


# ── Request / Response Models ───────────────────────────────────────

class ResearchRequest(BaseModel):
    """What a client sends to POST /research."""
    query: str = Field(..., min_length=3, description="Research topic to investigate")
    max_papers: int = Field(default=3, ge=1, le=10, description="Max papers to analyze")


# NEW (Phase 2g): nested models mirroring the dicts that come out of
# OrchestrationResult.paper_analyses. Defining these explicitly (rather
# than just typing paper_analyses as list[dict]) means FastAPI validates
# the shape AND documents it at /docs — same reasoning as every other
# Pydantic model in this file.

class ConceptOut(BaseModel):
    name: str
    summary: str


class RelationshipOut(BaseModel):
    concept_a: str
    concept_b: str
    relation: str


class PaperAnalysisOut(BaseModel):
    """One paper's structured analysis — what the UI's right-hand panel renders."""
    paper_id: str
    title: str
    local_pdf_path: str | None = None
    concepts: list[ConceptOut] = []
    relationships: list[RelationshipOut] = []


class ResearchResponse(BaseModel):
    """What POST /research sends back."""
    query: str
    report_markdown: str
    papers_found: int
    papers_analyzed: int
    errors: list[str]
    # NEW (Phase 2g): structured per-paper data, separate from the
    # markdown blob. The UI needs this to build the side panel (titles,
    # concept counts, PDF paths) without re-parsing markdown text.
    paper_analyses: list[PaperAnalysisOut] = []


class ReportSummary(BaseModel):
    """One entry in the GET /reports list."""
    filename: str
    created_at: str


class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool


# ── App Setup ─────────────────────────────────────────────────────────

app = FastAPI(
    title="ResearchPilot API",
    description="Autonomous research assistant: ArXiv + Neo4j + LLM agents",
    version="0.1.0",
)


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    neo4j_ok = False
    try:
        conn = Neo4jConnection()
        conn.connect()
        conn.close()
        neo4j_ok = True
    except Exception as e:
        logger.warning(f"Health check: Neo4j connection failed: {e}")

    return HealthResponse(
        status="ok" if neo4j_ok else "degraded",
        neo4j_connected=neo4j_ok,
    )


@app.post("/research", response_model=ResearchResponse)
def trigger_research(request: ResearchRequest):
    request_id = request.query[:40]
    logger.info(f"POST /research — query='{request_id}', max_papers={request.max_papers}")

    try:
        orchestrator = Orchestrator(max_papers=request.max_papers)
        result = orchestrator.run(request.query)
    except Exception as e:
        logger.error(f"Pipeline crashed for query '{request_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    return ResearchResponse(
        query=result.query,
        report_markdown=result.to_report(),
        papers_found=result.papers_found,
        papers_analyzed=result.papers_analyzed,
        errors=result.errors,
        # Pydantic validates/coerces these plain dicts into
        # PaperAnalysisOut/ConceptOut/RelationshipOut automatically
        # because the field is typed as list[PaperAnalysisOut] —
        # no manual conversion loop needed.
        paper_analyses=result.paper_analyses,
    )


@app.get("/reports", response_model=list[ReportSummary])
def list_reports():
    if not REPORTS_DIR.exists():
        return []

    files = sorted(REPORTS_DIR.glob("*.md"), reverse=True)

    return [
        ReportSummary(
            filename=f.name,
            created_at=f.name[:19],
        )
        for f in files
    ]


@app.get("/reports/{filename}")
def get_report(filename: str):
    filepath = REPORTS_DIR / filename

    if not filepath.resolve().is_relative_to(REPORTS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    return {"filename": filename, "content": filepath.read_text(encoding="utf-8")}


@app.get("/graph/stats")
def graph_stats():
    try:
        conn = Neo4jConnection()
        conn.connect()
        summary = get_graph_summary(conn)
        conn.close()
        return summary
    except Exception as e:
        logger.error(f"Graph stats query failed: {e}")
        raise HTTPException(status_code=503, detail=f"Could not reach graph database: {e}")