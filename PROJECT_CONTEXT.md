# ResearchPilot AI — Project Context
# Paste this at the start of any new Claude conversation

---

## 🎯 Project Goal
A 5-agent autonomous research assistant that searches ArXiv,
builds a Neo4j knowledge graph, identifies research gaps,
and generates structured research reports — with a scheduler,
REST API, and web UI on top.

## 👤 Developer Profile
- Python level: Beginner (learning through this project)
- Target role: AI/ML Engineer
- Prior exposure: LangChain, Neo4j, Docker, FastAPI (basics)
- Needs: Full explanation of every code decision
- OS: Windows — venv at C:\Users\aryan\Documents\researchpilot

## 🤖 Teaching Style Agreed Upon
Every code block follows this structure:
- 🧠 CONCEPT FIRST → What and why
- 🔨 THE CODE → Implementation
- 🔍 LINE BY LINE → What each part does
- 💼 INTERVIEW ANGLE → What interviewers ask

⚠️ WORKFLOW REMINDER: Always include the COMPLETE, copy-pasteable code
file in the response itself — not just a description of changes or
test output. (This was missed a couple of times in the Week 4 session —
showing sandbox verification logs is good practice, but the actual
final file block must always follow it.)

---

## 🏗️ Architecture — STATUS: ALL 4 WEEKS COMPLETE ✅

### 5 Agents
| Agent | File | Status |
|---|---|---|
| Orchestrator | agents/orchestrator.py | ✅ Complete |
| ArXiv Agent | agents/arxiv_agent.py | ✅ Complete (bug fixed — see below) |
| GraphRAG Agent | agents/graphrag_agent.py | ✅ Complete |
| Web Search Agent | agents/websearch_agent.py | ✅ Complete |
| Critic Agent | agents/critic_agent.py | ✅ Complete |

### Tech Stack
- LLM: meta/llama-3.1-8b-instruct (via NVIDIA NIM / langchain-nvidia-ai-endpoints)
- Agent Framework: LangGraph (used selectively — see Key Decisions)
- Graph Database: Neo4j 5.13 (Docker)
- Search: ArXiv API + Tavily
- API: FastAPI + Uvicorn
- UI: Gradio 4.44.0 — calls API over HTTP via `requests`, does NOT import
  orchestrator directly (clean client/server separation)
- Scheduler: APScheduler — currently in RUN_ONCE mode (see below)
- Observability: LangSmith
- Testing: pytest (not yet written)

---

## 📁 Project Structure
```
researchpilot/
├── agents/
│   ├── orchestrator.py        ✅ Complete
│   ├── arxiv_agent.py         ✅ Complete (bug fixed)
│   ├── graphrag_agent.py      ✅ Complete
│   ├── websearch_agent.py     ✅ Complete
│   └── critic_agent.py        ✅ Complete
├── pipeline/
│   ├── arxiv_fetcher.py       ✅ Complete
│   ├── pdf_parser.py          ✅ Complete
│   └── neo4j_ingestor.py      ✅ Complete
├── graph/
│   ├── connection.py          ✅ Complete
│   └── queries.py             ✅ Complete
├── api/routes.py              ✅ Complete — 5 endpoints, tested
├── ui/app.py                  ✅ Complete — 3 tabs, tested end-to-end
├── scheduler/update_job.py    ✅ Complete — RUN_ONCE=True ⚠️ (toggle later)
├── tests/                     ⏳ Not started
├── watched_topics.json        ✅ Complete (project root)
├── reports/                   ✅ Auto-created, holds timestamped .md reports
├── config.py                  ✅ Complete
└── main.py                    ✅ Complete — starts API+UI together, tested
```

---

## ✅ Progress

### Week 1 — Complete
- [x] Folder structure, venv, requirements.txt, .env + config.py
- [x] ArXiv fetcher, Neo4j Docker + connection manager + schema
- [x] Neo4j ingestor (MERGE-based, idempotent), pdf_parser.py
- [x] End-to-end pipeline test passed

### Week 2 — Complete
- [x] arxiv_agent.py, graphrag_agent.py (direct loop, not LangGraph)
- [x] queries.py, orchestrator.py
- [x] Migrated Gemini → NVIDIA NIM (ChatNVIDIA)
- [x] Fixed ArXiv 429s, structured output None returns, Llama single-tool-call limit

### Week 3 — Complete
- [x] websearch_agent.py, critic_agent.py
- [x] Full pipeline test passed (all 4 stages)
- [x] scheduler/update_job.py — APScheduler, reads watched_topics.json,
      saves timestamped reports, per-topic error isolation tested
- [x] FIXED: arxiv_agent papers_found=0 bug (full detail below)
- [x] FIXED: sys.path import error when running scheduler as a script
- [x] Added RUN_ONCE toggle to scheduler for one-shot testing

### Week 4 — Complete
- [x] api/routes.py — FastAPI: /health, POST /research, /reports,
      /reports/{filename}, /graph/stats. Synchronous pipeline execution
      (documented tradeoff — background job queue is the future upgrade
      path if a single request needs to scale beyond ~5 min)
- [x] ui/app.py — Gradio, 3 tabs (Run Research / Past Reports / Graph
      Stats), calls api/routes.py over HTTP, REQUEST_TIMEOUT=300s
- [x] main.py — starts uvicorn + Gradio as subprocesses, polls /health
      before declaring ready, clean try/finally shutdown on Ctrl+C or
      child-process crash
- [x] Fixed two dependency-version issues (audioop-lts, huggingface_hub
      pin — see Known Issues)
- [x] Full system verified end-to-end on developer's real machine:
      main.py → both servers up → real query run through UI → report
      generated → visible in Past Reports tab → graph stats populated

---

## ⚙️ Environment Details

### Running Services
- Neo4j: Docker container 'researchpilot-neo4j'
  - Browser UI: http://localhost:7474 | Bolt: bolt://localhost:7687
  - Username: neo4j | Password: researchpilot123
- API: http://127.0.0.1:8000 (interactive docs at /docs)
- UI: http://127.0.0.1:7860

### Start Commands
```bash
# Start Neo4j
docker start researchpilot-neo4j

# Activate venv (Windows)
cd C:\Users\aryan\Documents\researchpilot
venv\Scripts\activate

# Run everything (recommended — one command)
python main.py

# OR run API + UI separately (two terminals, useful for debugging)
uvicorn api.routes:app --reload --port 8000
python ui/app.py

# Run scheduler once (currently RUN_ONCE=True in scheduler/update_job.py)
python scheduler/update_job.py
```

### Re-run Schema on Fresh Neo4j Container
```bash
python3 -c "
from graph.connection import Neo4jConnection, create_schema
conn = Neo4jConnection(); create_schema(conn); conn.close()
"
```

---

## ⚠️ Known Issues / Resolved (full history)

### Resolved in Week 3-4 session:
- ✅ FIXED: `arxiv_agent.papers_found=0` bug — `run_arxiv_agent()` never
  returned a `"papers"` key, only `query`/`summary`/`message_count`.
  Orchestrator's `.get("papers", [])` always got `[]`, so Stage 2
  (GraphRAG) was silently skipped even though papers downloaded fine.
  FIX: after the LangGraph loop finishes, call
  `_fetcher.fetch_and_download(query, max_results=3)` directly to get
  real `Paper` objects, convert to dicts (filtering out any with no
  `local_pdf_path`), include as `"papers"` key in the return dict.
  ⚠️ KNOWN SIDE EFFECT: ArXiv now gets searched twice per run (once
  inside the agent's tool call, once in this direct call) — adds
  latency but doesn't trigger 429s given existing rate-limit config.
  Worth revisiting if pipeline speed becomes a priority.
- ✅ FIXED: `ModuleNotFoundError: No module named 'agents'` when running
  `python scheduler/update_job.py` or `api/routes.py` directly — Python
  only adds the *script's own folder* to sys.path, not the project
  root. FIX: `sys.path.insert(0, str(Path(__file__).parent.parent))`
  added to the top of both scheduler/update_job.py and api/routes.py,
  before any project-internal imports.
- ✅ FIXED: `ModuleNotFoundError: No module named 'audioop'` /
  `'pyaudioop'` when running `ui/app.py` — Python 3.13 removed the
  `audioop` stdlib module (PEP 594); pydub (a Gradio dependency for
  audio components never actually used) still imports it at startup.
  FIX: `pip install audioop-lts` (a compatibility shim package, only
  installs on Python 3.13+). Added to requirements.txt as:
  `audioop-lts; python_version >= "3.13"`
- ✅ FIXED: `ImportError: cannot import name 'HfFolder' from
  'huggingface_hub'` — version skew between installed gradio (4.44.0,
  expects old huggingface_hub API with HfFolder) and a too-new
  huggingface_hub that already removed it. FIX: pinned
  `pip install "huggingface_hub<1.0"` (resolved at 0.36.2, confirmed
  working). Added to requirements.txt as: `huggingface-hub<1.0`
- ✅ FIXED: UI request timing out at 120s on real (non-stubbed) pipeline
  runs through Gradio — the full pipeline (ArXiv + 3-4 LLM calls +
  Tavily + critic) legitimately takes 1-3+ minutes; 120s was too
  aggressive. FIX: raised `REQUEST_TIMEOUT` in ui/app.py from 120 to
  300. Worth remembering: client timeout ≠ server cancellation — the
  orchestrator kept running server-side even after Gradio gave up
  waiting on the old 120s value.

### Resolved earlier (Week 1-2):
- ✅ FIXED: Gemini quota (20 req/day) — migrated to NVIDIA NIM
- ✅ FIXED: Two LLM calls per paper — merged into one via PaperAnalysis schema
- ✅ FIXED: ArXiv HTTP 429 — delay_seconds=10, num_retries=3 on arxiv.Client,
  plus time.sleep(3) before each search call. Use specific queries, not
  broad ones like "transformers"
- ✅ FIXED: structured_llm.invoke() returning None — try/except + retry
  with simpler prompt + safe error return (never crashes pipeline)
- ✅ FIXED: Llama "single tool-call at once" LangGraph crash — removed
  LangGraph from graphrag_agent, replaced with direct for loop
- ✅ FIXED: TavilySearchResults deprecated — migrated to langchain-tavily
  package, TavilySearch class. Results are under ["results"] key now.
- ✅ FIXED: critic_agent LLM returning None — three-layer defense catches
  it, shows "unavailable" but pipeline continues.

### Still open / deferred (not bugs, known tradeoffs):
- ⚠️ `scheduler/update_job.py` has `RUN_ONCE = True` set near the bottom
  of the file (for testing). Flip to `False` to resume the normal
  hourly interval loop via `start_scheduler()`.
- ⚠️ `/research` in api/routes.py runs the pipeline **synchronously** —
  a request blocks for the full pipeline duration (1-3+ min). This was
  an explicit, documented choice for simplicity. Future upgrade path if
  needed: return a `job_id` immediately, add a `/status/{job_id}`
  endpoint, run the pipeline in a background task/thread.
- ⚠️ Double ArXiv search per run (see arxiv_agent fix above) — acceptable
  for now given rate-limit headroom, but a known inefficiency.
- ⚠️ Neo4j UnknownLabelWarning on fresh container — harmless, schema
  just needs re-running (see command above).
- ⚠️ No tests written yet (tests/ folder is empty).
- ⚠️ `process.terminate()` in main.py behaves slightly differently on
  Windows (closer to a hard kill via TerminateProcess) vs Linux/Mac
  (graceful SIGTERM) — both reliably stop the child processes, but
  don't expect to see uvicorn's graceful "Shutting down..." log lines
  on Windows shutdown.

---

## 📦 File Signatures

### config.py
- Pattern: module-level variables (NOT Pydantic BaseSettings)
- Import style: `import config` then `config.NVIDIA_API_KEY`
- NVIDIA_API_KEY, NVIDIA_MODEL, NEO4J_URI, NEO4J_USERNAME
- NEO4J_PASSWORD, TAVILY_API_KEY, LANGCHAIN_API_KEY
- MAX_PAPERS_PER_SEARCH, PDF_STORAGE_PATH, REPORT_STORAGE_PATH
- Fail-fast validation on startup

### pipeline/arxiv_fetcher.py
- class Paper (dataclass): paper_id, title, authors, abstract,
  published, pdf_url, local_pdf_path
- class ArXivFetcher:
  - client = arxiv.Client(page_size=5, delay_seconds=10, num_retries=3)
  - search_papers(query, max_results) -> List[Paper]  [time.sleep(3) at start]
  - download_pdf(paper) -> Optional[str]
  - fetch_and_download(query, max_results) -> List[Paper]

### pipeline/pdf_parser.py
- class PDFParser(max_pages=None):
  - extract_text(pdf_path) -> Optional[str]
  - extract_abstract(pdf_path) -> Optional[str]
  - _extract_with_pymupdf(pdf_path) -> str
  - _clean_text(raw_text) -> str

### pipeline/neo4j_ingestor.py
- class Neo4jIngestor(connection):
  - ingest_paper(paper) -> bool
  - ingest_papers(papers) -> dict
  - add_concept_to_paper(paper_id, concept_name)
  - link_related_concepts(concept_a, concept_b)
  - get_graph_stats() -> dict

### graph/connection.py
- class Neo4jConnection(uri, username, password):
  - connect(), get_session(), run_query(query, parameters), close()
- create_schema(conn) — creates constraints + indexes

### graph/queries.py
- get_all_concepts(conn) -> list[str]
- get_concepts_for_paper(conn, paper_id) -> list[str]
- get_related_concepts(conn, concept_name) -> list[str]
- get_papers_by_concept(conn, concept_name) -> list[dict]
- find_research_gaps(conn, min_papers=2) -> list[dict]
  — finds concepts in multiple papers with zero relationships (isolated nodes)
- get_most_connected_concepts(conn, top_n=10) -> list[dict]
- get_graph_summary(conn) -> dict {papers, concepts, relationships}

### agents/arxiv_agent.py ✅ BUG FIXED
- Tools: search_arxiv(query, max_results), fetch_and_download_papers(query, max_results)
- State: ArXivAgentState (messages, query, papers_found)
- run_arxiv_agent(query) -> dict {query, summary, papers: list[dict], message_count}
  papers dict keys: paper_id, title, local_pdf_path
- FIX APPLIED: after app.invoke(), directly calls
  _fetcher.fetch_and_download(query, max_results=3) to populate the
  "papers" key with real data (the LangGraph tool-call results never
  made it back out otherwise). Filters out papers with no local_pdf_path.

### agents/graphrag_agent.py
- Pydantic schemas:
  - Relationship(concept_a, concept_b, relation)
  - PaperAnalysis(concepts: list[str], relationships: list[Relationship])
- Tools: analyze_paper(pdf_path, paper_id) — ONE LLM call for both concepts + relationships
         get_graph_statistics()
- Lazy Neo4j init: get_ingestor() -> Neo4jIngestor
- ⚠️ NO LangGraph — uses direct for loop (Llama only supports single tool-call)
- run_graphrag_agent(papers: list[dict]) -> dict
  {status, processed, errors: list[str], papers: list[dict]}

### agents/websearch_agent.py
- Pydantic schemas:
  - WebFinding(title, summary, relevance, source_url)
  - WebSearchAnalysis(findings: list[WebFinding], overall_summary, gaps_identified)
- build_search_tool(max_results) -> TavilySearch  [from langchain_tavily]
  - search_depth="advanced", include_answer=True, include_raw_content=False
  - ⚠️ TavilySearch.invoke() returns a dict — actual results under ["results"] key
- analyze_web_results(query, raw_results, llm_with_schema) -> Optional[WebSearchAnalysis]
  - Three-layer defense: try → retry simpler prompt → return None
- run_websearch_agent(query, max_results=5) -> dict
  {query, status, findings, overall_summary, gaps_identified, raw_result_count, errors}
- _error_return(query, reason) -> dict
- _raw_to_findings(raw_results) -> list[dict]  [fallback if LLM fails]

### agents/critic_agent.py
- Pydantic schemas:
  - DimensionScore(score: int ge=0 le=10, reasoning: str)
  - CritiqueResult(relevance, coverage, evidence_quality, gap_identification,
    actionability: DimensionScore, overall_score: int 0-100, verdict: str,
    strengths: list[str], weaknesses: list[str], recommendation: str)
- score_to_verdict(score) -> str  [maps 0-100 to excellent/good/acceptable/needs_improvement]
- critique_report(query, report, llm_with_schema) -> Optional[CritiqueResult]
  - Three-layer defense, report capped at 3000 chars
- run_critic_agent(query, report) -> dict
  {status, overall_score, verdict, dimensions: dict, strengths, weaknesses,
   recommendation, errors}
- _error_return(query, reason) -> dict

### agents/orchestrator.py
- @dataclass OrchestrationResult:
  query, papers_found, papers_analyzed, graph_summary,
  research_gaps, hub_concepts, errors, started_at, completed_at,
  web_findings, web_summary, critique
  - to_report() -> str  (markdown report with all sections)
  - _format_web_findings() -> str
  - _format_critique() -> str
- class Orchestrator(max_papers=3):
  - run(query) -> OrchestrationResult
  - Stage 1: run_arxiv_agent(query)
  - Stage 2: run_graphrag_agent(papers[:max_papers])
  - Stage 2.5: run_websearch_agent(query, max_results=5)
  - Stage 3: graph queries (summary + gaps + hubs)
  - Stage 4: run_critic_agent(query, partial_report)
  - Each stage wrapped in try/except — pipeline degrades, never crashes
  - _build_partial_report(result) -> str  [feeds critic; avoids calling to_report() early]
- run_pipeline(query, max_papers=3) -> str  (facade, returns markdown)

### scheduler/update_job.py ✅ NEW
- Reads watched_topics.json {"topics": [list of query strings]}
- load_topics() -> list[str]  [fails soft — empty list on missing/malformed file]
- save_report(query, report) -> Path  [timestamped filename: YYYY-MM-DD_HH-MM-SS_slug.md]
- run_all_watched_topics() — loops topics, try/except PER TOPIC so one
  failure doesn't kill the rest, calls run_pipeline() + save_report()
- start_scheduler() — BlockingScheduler, interval trigger, hours=1,
  next_run_time=datetime.now() (fires immediately on startup too)
- ⚠️ RUN_ONCE = True toggle at bottom of file — when True, calls
  run_all_watched_topics() once and exits instead of starting the
  scheduler loop. Flip to False to resume normal hourly operation.
- Has sys.path.insert fix at top (see Known Issues)

### api/routes.py ✅ NEW
- Pydantic models: ResearchRequest (query: str min_length=3,
  max_papers: int 1-10), ResearchResponse, ReportSummary, HealthResponse
- GET /health — actually tests Neo4j connection, not just "server is up"
- POST /research — runs Orchestrator synchronously, returns full report
  + counts + errors. Wraps in try/except -> HTTPException 500 on crash.
- GET /reports — lists reports/ folder .md files, newest first
- GET /reports/{filename} — returns one report's content. SECURITY:
  path-traversal guard via filepath.resolve().is_relative_to(REPORTS_DIR)
  before reading — verified this blocks "../" attempts even if Starlette's
  own URL-layer protection weren't there (defense in depth, tested both layers)
- GET /graph/stats — wraps get_graph_summary(), 503 if Neo4j unreachable
- Has sys.path.insert fix at top (see Known Issues)

### ui/app.py ✅ NEW
- API_BASE_URL = "http://localhost:8000" (hardcoded — fine for same-machine dev)
- REQUEST_TIMEOUT = 300  [raised from 120 after real-world testing — see Known Issues]
- call_research_api(query, max_papers) -> tuple[report_md, status_msg]
  - Handles ConnectionError (API not running) and Timeout separately,
    with actionable messages instead of raw stack traces
- fetch_report_list() -> list[str]  [filenames for dropdown]
- fetch_report_content(filename) -> str
- fetch_graph_stats() -> tuple[stats_md, health_status]
  - Checks /health first (clearer error attribution if Neo4j is the
    actual problem vs the API itself being down)
- Gradio gr.Blocks with 3 gr.Tab: "🔍 Run Research", "📂 Past Reports",
  "📊 Graph Stats". demo.load() auto-fetches graph stats on page open.
- Does NOT import agents.orchestrator — pure HTTP client of api/routes.py

### main.py ✅ NEW
- wait_for_api(timeout=30) -> bool  [polls GET /health every 0.5s instead
  of a fixed sleep — adapts to actual startup time]
- main():
  - Starts uvicorn via subprocess.Popen([sys.executable, "-m", "uvicorn", ...],
    cwd=PROJECT_ROOT) — sys.executable guarantees same venv is used
  - Waits for API health before starting UI
  - Starts ui/app.py via subprocess.Popen similarly
  - while True loop: polls both processes' .poll() every 1s, breaks if
    either exits unexpectedly
  - try/except KeyboardInterrupt + finally block: ALWAYS attempts clean
    shutdown (terminate() -> wait(timeout=5) -> kill() fallback) for
    both children, regardless of how main() exited (Ctrl+C, crash, or
    early return after failed health check)
  - Verified end-to-end on real machine: starts both, detects crashes,
    shuts down both cleanly

---

## 🔑 Key Decisions Made
1. NVIDIA NIM (meta/llama-3.1-8b-instruct) — free tier, replaces Gemini
2. ChatNVIDIA from langchain-nvidia-ai-endpoints — drop-in LangChain replacement
3. MERGE not CREATE in Cypher — idempotency
4. Dependency injection in Neo4jIngestor
5. Logging over print() throughout
6. @dataclass for Paper object
7. Gradio over CSS/JS — right tool for AI/ML engineer portfolio
8. Pydantic structured output (.with_structured_output()) — guarantees schema
9. Lazy initialization for Neo4j in graphrag_agent
10. ⭐ GraphRAG uses direct for loop, NOT LangGraph — Llama 3.1 8B rejects
    parallel/sequential multi-tool calls in LangGraph. Rule learned:
    use LangGraph only when agent needs to REASON about what to do next,
    not when the workflow is deterministic
11. PaperAnalysis unified schema — one LLM call per paper (concepts + relationships)
12. Domain-agnostic prompts — never say "ML/AI concepts", say "key concepts"
    so the system works for any research domain (biology, physics, etc.)
13. text[:2500] cap in analyze_paper — controls tokens, reduces None returns
14. Three-layer defense in analyze_paper: try/except → retry simpler prompt →
    safe error return. One bad paper never crashes the pipeline
15. ArXiv client config: delay_seconds=10, num_retries=3, plus time.sleep(3)
    before search. Use specific queries, not broad ones like "transformers"
16. max_pages=5 in PDFParser — balance between speed and extraction quality
17. config.py uses module-level variables NOT Pydantic BaseSettings —
    import as `import config` then `config.KEY_NAME`
18. TavilySearch (langchain-tavily) returns full dict — extract ["results"]
    for the actual list. Old TavilySearchResults returned flat list directly.
19. score_to_verdict() overrides LLM verdict string — numeric score is more
    reliable than free-text enum from Llama; derive don't trust
20. _build_partial_report() feeds critic instead of to_report() — avoids
    calling _format_critique() before critique is set; also gives critic
    cleaner prose input than formatted markdown
21. ⭐ arxiv_agent fix: re-call fetch_and_download() directly after the
    LangGraph loop instead of trying to extract Paper data from tool-call
    message history. Simpler than parsing ToolMessage content; trade-off
    is one extra ArXiv search per run.
22. sys.path.insert(0, project_root) at the top of any script meant to be
    run directly (scheduler/update_job.py, api/routes.py) — needed because
    Python only auto-adds the script's own folder to sys.path, not the
    project root, when running `python some/folder/script.py`.
23. Scheduler reads topics from watched_topics.json (not hardcoded, not
    CLI args) — lets the user edit "what to research" without touching code.
24. Per-topic (scheduler) and per-stage (orchestrator) try/except — same
    graceful-degradation philosophy applied at every layer of the system.
25. UI calls API over HTTP (requests library) rather than importing
    Orchestrator directly — deliberate architectural choice for realistic
    client/server decoupling, even though it adds latency and two
    processes to manage. main.py exists specifically to make that
    two-process tradeoff invisible to the end user (one command, one
    cleanup path).
26. /research runs synchronously — explicit, documented, deferred tradeoff.
    Background job queue is the natural next upgrade if needed later.
27. Path-traversal guard on GET /reports/{filename} using
    Path.resolve().is_relative_to() — standard pattern any time a
    filename from user input is used to build a filesystem path.
28. main.py uses subprocess.Popen + poll()/terminate()/kill() rather than
    threading — uvicorn and Gradio each want to own their own event loop,
    so separate OS processes avoid asyncio conflicts.

---

## 💼 Interview Concepts Covered
- Separation of concerns (folder structure)
- Virtual environments (dependency isolation)
- Secrets management (.env + config.py)
- Fail-fast validation
- @dataclass decorator
- List comprehensions
- Type hints (Optional, List)
- Context managers (with statement)
- Singleton pattern (connection manager)
- Dependency injection
- Idempotency (MERGE vs CREATE)
- Rate limiting (time.sleep + client config)
- Parameterized queries (injection prevention)
- Loose coupling (LangChain provider abstraction)
- LangGraph state machines vs linear chains — and when NOT to use LangGraph
- Tool binding (LLM + tools)
- Structured outputs with Pydantic (.with_structured_output())
- Lazy initialization
- temperature=0 for deterministic agents
- add_messages reducer in LangGraph state
- Schema consolidation (PaperAnalysis — one call vs two)
- Graceful degradation (try/except per stage in orchestrator, per topic
  in scheduler)
- Facade pattern (run_pipeline() hides Orchestrator class)
- Repository pattern (queries.py — graph queries in one place)
- Graph-based research gap detection (isolated but popular concept nodes)
- Domain-agnostic prompt design
- Three-layer LLM reliability defense (try → retry → safe error)
- LLM model constraints (single tool-call limitation in smaller models)
- Rubric-based LLM evaluation (multi-dimensional scoring in critic agent)
- Meta-agent pattern (one LLM evaluating another LLM's output)
- Pydantic field validators (ge=, le= for range enforcement)
- Consistent return shapes (_error_return helpers in every agent)
- Library migration debugging (print raw output before assuming data shape)
- Deriving values from numbers vs trusting LLM free-text strings
- Python import resolution (sys.path, script dir vs project root vs
  python -m module execution)
- HTTP API design (Pydantic request/response models, path vs query vs
  body parameters, status codes, FastAPI auto-docs)
- Path traversal prevention (resolve() + is_relative_to())
- Client/server decoupling (UI as one possible client of an API)
- Health checks that test real dependencies, not just "process is alive"
- Client-side timeout vs server-side cancellation (they're independent —
  a client giving up doesn't stop server-side work)
- Process orchestration (subprocess.Popen, poll(), terminate()/kill()
  with timeout fallback)
- try/finally for guaranteed cleanup across multiple exit paths
- Polling vs fixed sleep for "wait until ready" logic
- Transitive dependency breakage (pydub→audioop, gradio→huggingface_hub)
  and version pinning as the fix
- Defense in depth (testing a security check at multiple layers
  independently, not just trusting the first one that blocks an attack)

---

## 🔜 Next Steps (not started — pick up here)
Pick ONE when resuming:
1. **Tests** — pytest coverage for agents, pipeline, graph queries, and
   the new api/routes.py endpoints (FastAPI TestClient pattern already
   proven to work well, demonstrated during Week 4 build/verification)
2. **Portfolio polish** — README with architecture diagram, screenshots
   of the Gradio UI, a short demo GIF/video, clear setup instructions
3. **Background job queue** — upgrade POST /research from synchronous to
   async with job_id + polling, removing the current ~5 min request
   ceiling
4. **Toggle scheduler back** — flip RUN_ONCE to False in
   scheduler/update_job.py when ready to resume normal hourly cadence
5. **Revisit double ArXiv search** — decide if the arxiv_agent fix's
   extra search call is worth optimizing away now that the system is
   otherwise stable
