# ResearchPilot AI — Project Context
# Paste this at the start of any new Claude conversation

---

## 🎯 Project Goal
A 5-agent autonomous research assistant that searches ArXiv,
builds a Neo4j knowledge graph, identifies research gaps,
and generates structured research reports.

## 👤 Developer Profile
- Python level: Beginner (learning through this project)
- Target role: AI/ML Engineer
- Prior exposure: LangChain, Neo4j, Docker, FastAPI (basics)
- Needs: Full explanation of every code decision

## 🤖 Teaching Style Agreed Upon
Every code block follows this structure:
- 🧠 CONCEPT FIRST → What and why
- 🔨 THE CODE → Implementation
- 🔍 LINE BY LINE → What each part does
- 💼 INTERVIEW ANGLE → What interviewers ask

---

## 🏗️ Architecture

### 5 Agents
| Agent | File | Status |
|---|---|---|
| Orchestrator | agents/orchestrator.py | ✅ Complete |
| ArXiv Agent | agents/arxiv_agent.py | ✅ Complete |
| GraphRAG Agent | agents/graphrag_agent.py | ✅ Complete |
| Web Search Agent | agents/websearch_agent.py | ⏳ Week 3 |
| Critic Agent | agents/critic_agent.py | ⏳ Week 3 |

### Tech Stack
- LLM: meta/llama-3.1-8b-instruct (via NVIDIA NIM / langchain-nvidia-ai-endpoints)
- Agent Framework: LangGraph (used selectively — see Key Decisions)
- Graph Database: Neo4j 5.13 (Docker)
- Search: ArXiv API + Tavily
- API: FastAPI + Uvicorn
- UI: Gradio
- Scheduler: APScheduler
- Observability: LangSmith
- Testing: pytest

---

## 📁 Project Structure
```
researchpilot/
├── agents/
│   ├── orchestrator.py        ✅ Complete
│   ├── arxiv_agent.py         ✅ Complete
│   ├── graphrag_agent.py      ✅ Complete
│   ├── websearch_agent.py     ⏳ Week 3
│   └── critic_agent.py        ⏳ Week 3
├── pipeline/
│   ├── arxiv_fetcher.py       ✅ Complete
│   ├── pdf_parser.py          ✅ Complete
│   └── neo4j_ingestor.py      ✅ Complete
├── graph/
│   ├── connection.py          ✅ Complete
│   └── queries.py             ✅ Complete
├── api/routes.py              ⏳ Week 4
├── ui/app.py                  ⏳ Week 4
├── scheduler/update_job.py    ⏳ Week 3
├── tests/                     ⏳ Ongoing
├── config.py                  ✅ Complete
└── main.py                    ⏳ Week 4
```

---

## ✅ Progress

### Week 1 — Complete
- [x] Folder structure created
- [x] Virtual environment (python3 -m venv venv)
- [x] requirements.txt installed
- [x] .env + config.py with validation
- [x] ArXiv fetcher (searches + downloads PDFs)
- [x] Neo4j running in Docker
- [x] Neo4j connection manager + schema
- [x] Neo4j ingestor (MERGE-based, idempotent)
- [x] pdf_parser.py (PyMuPDF text extraction)
- [x] End-to-end pipeline test passed

### Week 2 — Complete
- [x] arxiv_agent.py — LangGraph agent, searches + downloads papers
- [x] graphrag_agent.py — rebuilt as direct loop (see Key Decisions #10)
- [x] queries.py — graph query helpers
- [x] orchestrator.py — coordinates arxiv + graphrag agents
- [x] Migrated from Gemini to NVIDIA NIM (ChatNVIDIA)
- [x] Fixed ArXiv HTTP 429 rate limiting
- [x] Fixed structured output returning None (Llama reliability)
- [x] Fixed Llama single-tool-call constraint in LangGraph

### Week 3 — Up Next
- [ ] websearch_agent.py — Tavily web search agent
- [ ] critic_agent.py — evaluates and scores research reports
- [ ] scheduler/update_job.py — APScheduler periodic runs

---

## ⚙️ Environment Details

### Running Services
- Neo4j: Docker container named 'researchpilot-neo4j'
  - Browser UI: http://localhost:7474
  - Bolt port: bolt://localhost:7687
  - Username: neo4j
  - Password: researchpilot123

### Start Commands
```bash
# Start Neo4j
docker start researchpilot-neo4j

# Activate virtual environment (Windows)
cd C:\Users\aryan\Documents\researchpilot
venv\Scripts\activate
```

### Re-run Schema on Fresh Neo4j Container
```bash
python3 -c "
from graph.connection import Neo4jConnection, create_schema
conn = Neo4jConnection(); create_schema(conn); conn.close()
"
```

### ⚠️ Known Issues / Resolved
- ✅ FIXED: Gemini quota (20 req/day) — migrated to NVIDIA NIM
- ✅ FIXED: Two LLM calls per paper — merged into one via PaperAnalysis schema
- ✅ FIXED: ArXiv HTTP 429 — added delay_seconds=10, num_retries=3 to arxiv.Client
  and time.sleep(3) before each search call. Use specific queries, not broad ones
  like "transformers"
- ✅ FIXED: structured_llm.invoke() returning None — added try/except + retry
  with simpler prompt + safe error return (never crashes pipeline)
- ✅ FIXED: Llama "single tool-call at once" LangGraph crash — removed LangGraph
  from graphrag_agent, replaced with direct for loop (see Key Decisions #10)
- ⚠️  Neo4j UnknownLabelWarning on fresh container — harmless, schema just needs
  re-running (see command above)

---

## 📦 File Signatures

### config.py
- NVIDIA_API_KEY, NVIDIA_MODEL, NEO4J_URI, NEO4J_USERNAME
- NEO4J_PASSWORD, TAVILY_API_KEY, LANGCHAIN_API_KEY
- MAX_PAPERS_PER_SEARCH, PDF_STORAGE_PATH, REPORT_STORAGE_PATH
- Fail-fast validation on startup

### pipeline/arxiv_fetcher.py
- class Paper (dataclass): paper_id, title, authors, abstract,
  published, pdf_url, local_pdf_path
- class ArXivFetcher:
  - client = arxiv.Client(page_size=5, delay_seconds=10, num_retries=3)
  - search_papers(query, max_results) -> List[Paper]  [has time.sleep(3) at start]
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

### agents/arxiv_agent.py
- Tools: search_arxiv(query, max_results), fetch_and_download_papers(query, max_results)
- State: ArXivAgentState (messages, query, papers_found)
- run_arxiv_agent(query) -> dict {query, summary, papers: list[dict]}
  papers dict keys: paper_id, title, local_pdf_path

### agents/graphrag_agent.py
- Pydantic schemas:
  - Relationship(concept_a, concept_b, relation)
  - PaperAnalysis(concepts: list[str], relationships: list[Relationship])
- Tools: analyze_paper(pdf_path, paper_id) — ONE LLM call for both concepts + relationships
         get_graph_statistics()
- Lazy Neo4j init: get_ingestor() -> Neo4jIngestor
- ⚠️  NO LangGraph — uses direct for loop (Llama only supports single tool-call)
- run_graphrag_agent(papers: list[dict]) -> dict
  {status, processed, errors: list[str], papers: list[dict]}
  papers dict keys: paper_id, title, local_pdf_path

### agents/orchestrator.py
- @dataclass OrchestrationResult:
  query, papers_found, papers_analyzed, graph_summary,
  research_gaps, hub_concepts, errors, started_at, completed_at
  - to_report() -> str  (markdown report)
- class Orchestrator(max_papers=3):
  - run(query) -> OrchestrationResult
  - Stage 1: run_arxiv_agent(query)
  - Stage 2: run_graphrag_agent(papers[:max_papers])
  - Stage 3: graph queries (summary + gaps + hubs)
  - Each stage wrapped in try/except — pipeline degrades, never crashes
- run_pipeline(query, max_papers=3) -> str  (facade, returns markdown)

---

## 🔜 Next Steps (Week 3)
1. websearch_agent.py — Tavily search, supplements ArXiv with web results
2. critic_agent.py — scores papers/reports for relevance and quality
3. scheduler/update_job.py — APScheduler for periodic pipeline runs
4. Then Week 4: FastAPI routes + Gradio UI + main.py

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
- Graceful degradation (try/except per stage in orchestrator)
- Facade pattern (run_pipeline() hides Orchestrator class)
- Repository pattern (queries.py — graph queries in one place)
- Graph-based research gap detection (isolated but popular concept nodes)
- Domain-agnostic prompt design
- Three-layer LLM reliability defense (try → retry → safe error)
- LLM model constraints (single tool-call limitation in smaller models)
