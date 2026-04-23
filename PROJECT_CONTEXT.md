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
| Orchestrator | agents/orchestrator.py | ⏳ Week 2 |
| ArXiv Agent | agents/arxiv_agent.py | ✅ Complete |
| GraphRAG Agent | agents/graphrag_agent.py | ✅ Complete |
| Web Search Agent | agents/websearch_agent.py | ⏳ Week 3 |
| Critic Agent | agents/critic_agent.py | ⏳ Week 3 |

### Tech Stack
- LLM: gemini-2.0-flash-lite-001 (via langchain-google-genai)
- Agent Framework: LangGraph
- Graph Database: Neo4j 5.13 (Docker)
- Search: ArXiv API + Tavily
- API: FastAPI + Uvicorn
- UI: Gradio
- Scheduler: APScheduler
- Observability: LangSmith
- Testing: pytest

---

## 📁 Project Structure
researchpilot/
├── agents/
│   ├── orchestrator.py        ⏳ Week 2
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
│   └── queries.py             ⏳ Week 2
├── api/routes.py              ⏳ Week 4
├── ui/app.py                  ⏳ Week 4
├── scheduler/update_job.py    ⏳ Week 3
├── tests/                     ⏳ Ongoing
├── config.py                  ✅ Complete
└── main.py                    ⏳ Week 4

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

### Week 2 — In Progress
- [x] arxiv_agent.py — LangGraph agent, searches + downloads papers
- [x] graphrag_agent.py — extracts concepts + relationships into Neo4j
- [ ] queries.py — graph query helpers
- [ ] orchestrator.py — coordinates all agents

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

# Activate virtual environment
cd /mnt/c/Users/aryan/Documents/researchpilot
source venv/bin/activate
```

### ⚠️ Known Issues
- Free tier Gemini quota (20 req/day) runs out fast with multi-agent runs
- Fix pending: combine extract_concepts + extract_relationships into
  one LLM call using a single Pydantic schema (PaperAnalysis)
- Neo4j container was recreated (lost old data) — schema needs
  re-running on fresh container start:
  python3 -c "
  from graph.connection import Neo4jConnection, create_schema
  conn = Neo4jConnection(); create_schema(conn); conn.close()
  "

### Key Decisions Made
1. gemini-2.0-flash-lite-001 — free tier, fast
2. MERGE not CREATE in Cypher (idempotency)
3. Dependency injection in Neo4jIngestor
4. Logging over print() throughout
5. @dataclass for Paper object
6. Gradio over CSS/JS (AI/ML engineer context)
7. Pydantic structured output (.with_structured_output()) 
   instead of prompting for JSON — guarantees schema
8. Lazy initialization for Neo4j in graphrag_agent
9. max_pages=5 in PDFParser for concept extraction (balance speed/quality)

---

## 📦 File Signatures

### config.py
- GOOGLE_API_KEY, GEMINI_MODEL, NEO4J_URI, NEO4J_USERNAME
- NEO4J_PASSWORD, TAVILY_API_KEY, LANGCHAIN_API_KEY
- MAX_PAPERS_PER_SEARCH, PDF_STORAGE_PATH, REPORT_STORAGE_PATH
- Fail-fast validation on startup

### pipeline/arxiv_fetcher.py
- class Paper (dataclass): paper_id, title, authors, abstract,
  published, pdf_url, local_pdf_path
- class ArXivFetcher:
  - search_papers(query, max_results) -> List[Paper]
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

### agents/arxiv_agent.py
- Tools: search_arxiv(query, max_results), fetch_and_download_papers(query, max_results)
- State: ArXivAgentState (messages, query, papers_found)
- run_arxiv_agent(query) -> dict {query, summary, message_count}

### agents/graphrag_agent.py
- Pydantic schemas: ConceptList, ConceptPair, RelationshipList
- Tools: extract_concepts_from_pdf(pdf_path, paper_id),
         extract_relationships_from_concepts(paper_id, concepts_json),
         get_graph_statistics()
- State: GraphRAGAgentState (messages, papers)
- run_graphrag_agent(papers: list[dict]) -> dict
  papers dict keys: paper_id, title, local_pdf_path

---

## 🔜 Next Steps
1. Fix quota issue: merge concept+relationship extraction into one LLM call
2. Build queries.py (graph query helpers for the agents)
3. Build orchestrator.py (coordinates arxiv + graphrag agents)
4. Then Week 3: websearch_agent.py + critic_agent.py

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
- Rate limiting (time.sleep)
- Parameterized queries (injection prevention)
- Loose coupling (LangChain provider abstraction)
- LangGraph state machines vs linear chains
- Tool binding (LLM + tools)
- Structured outputs with Pydantic (.with_structured_output())
- Lazy initialization
- temperature=0 for deterministic agents
- add_messages reducer in LangGraph state