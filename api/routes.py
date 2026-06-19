# api/routes.py
#
# FastAPI HTTP layer for ResearchPilot. Exposes the orchestrator
# pipeline, saved reports, and graph stats over HTTP so the Gradio
# UI (or any other client) doesn't need to import Python directly.

import logging
import sys
from pathlib import Path

# Same fix as scheduler/update_job.py — when api/routes.py is run
# (directly or via uvicorn), Python needs the project root on its
# import path to find the `agents`, `graph`, etc. packages.
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.orchestrator import Orchestrator
from graph.connection import Neo4jConnection
from graph.queries import get_graph_summary

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "reports"


# ── Request / Response Models ───────────────────────────────────────
# These are Pydantic models — same library as PaperAnalysis and
# CritiqueResult in your agents. There, Pydantic forced the LLM's
# output into a guaranteed shape. Here, it does the same job for
# HTTP traffic: FastAPI uses these to validate incoming JSON bodies
# AND to auto-generate the interactive docs at /docs.

class ResearchRequest(BaseModel):
    """What a client sends to POST /research."""
    query: str = Field(..., min_length=3, description="Research topic to investigate")
    max_papers: int = Field(default=3, ge=1, le=10, description="Max papers to analyze")
    # Field(..., min_length=3) — the "..." means this field is REQUIRED
    # (no default value). min_length=3 rejects empty/junk queries like
    # "a" before the request ever reaches your expensive pipeline.
    # ge=1, le=10 on max_papers — same range-enforcement pattern you
    # already used in critic_agent.py's DimensionScore (ge=0, le=10).


class ResearchResponse(BaseModel):
    """What POST /research sends back."""
    query: str
    report_markdown: str
    papers_found: int
    papers_analyzed: int
    errors: list[str]


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
    """
    Confirms the service is up AND can reach Neo4j.

    A health check that only says "the web server is running" is
    nearly useless in practice — the web server can be up while the
    database it depends on is down. Actually testing the Neo4j
    connection here means this endpoint tells you something true
    about whether /research will actually work.
    """
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
    """
    Runs the full pipeline synchronously for a given query.

    'Synchronous' means this HTTP request stays open and waits for
    the ENTIRE pipeline (ArXiv -> GraphRAG -> web search -> critic)
    to finish before responding — likely 30-60+ seconds. That's fine
    for now and for a portfolio demo. The known tradeoff: if a client
    has a short request timeout, or many people call this at once,
    this approach won't scale. The fix later is a background task
    queue (e.g. returning a job_id immediately and polling /status) —
    intentionally deferred, not a bug, just out of scope until needed.
    """
    request_id = request.query[:40]
    logger.info(f"POST /research — query='{request_id}', max_papers={request.max_papers}")

    try:
        orchestrator = Orchestrator(max_papers=request.max_papers)
        result = orchestrator.run(request.query)
    except Exception as e:
        # Anything that escapes the orchestrator's own internal
        # try/except (e.g. a totally unexpected crash) becomes a
        # proper HTTP 500 instead of FastAPI's generic stack trace.
        logger.error(f"Pipeline crashed for query '{request_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    return ResearchResponse(
        query=result.query,
        report_markdown=result.to_report(),
        papers_found=result.papers_found,
        papers_analyzed=result.papers_analyzed,
        errors=result.errors,
    )


@app.get("/reports", response_model=list[ReportSummary])
def list_reports():
    """
    Lists all saved reports from the reports/ folder.

    This is the same folder scheduler/update_job.py writes to — so
    this endpoint surfaces both scheduled background runs AND any
    manually saved reports, with no extra wiring needed.
    """
    if not REPORTS_DIR.exists():
        return []

    files = sorted(REPORTS_DIR.glob("*.md"), reverse=True)
    # reverse=True — since filenames start with a timestamp
    # (YYYY-MM-DD_HH-MM-SS_...), sorting alphabetically also sorts
    # chronologically. reverse=True means newest reports appear first,
    # which is what anyone browsing a report list actually wants.

    return [
        ReportSummary(
            filename=f.name,
            created_at=f.name[:19],  # "2026-06-19_14-30-05" prefix
        )
        for f in files
    ]


@app.get("/reports/{filename}")
def get_report(filename: str):
    """
    Returns the raw markdown content of one specific report.

    filename is a PATH parameter (part of the URL itself, e.g.
    GET /reports/2026-06-19_14-30-05_graph-neural-networks.md)
    as opposed to a query parameter (?filename=...) or a request
    body. FastAPI infers this from the {filename} in the route
    decorator matching the function argument name.
    """
    filepath = REPORTS_DIR / filename

    # Security check: prevent path traversal (e.g. someone requesting
    # filename="../../config.py" to read files outside reports/).
    # resolve() converts to an absolute path; the check confirms the
    # resolved path is still INSIDE reports/, not escaped via "..".
    if not filepath.resolve().is_relative_to(REPORTS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    return {"filename": filename, "content": filepath.read_text(encoding="utf-8")}


@app.get("/graph/stats")
def graph_stats():
    """
    Returns current graph summary: papers, concepts, relationships counts.

    Reuses get_graph_summary() from graph/queries.py directly — no
    new query logic needed, this endpoint is just an HTTP wrapper
    around code that already exists. Good example of NOT duplicating
    logic just because it's now being called from a new place.
    """
    try:
        conn = Neo4jConnection()
        conn.connect()
        summary = get_graph_summary(conn)
        conn.close()
        return summary
    except Exception as e:
        logger.error(f"Graph stats query failed: {e}")
        raise HTTPException(status_code=503, detail=f"Could not reach graph database: {e}")