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
| ArXiv Agent | agents/arxiv_agent.py | ⏳ Week 2 |
| GraphRAG Agent | agents/graphrag_agent.py | ⏳ Week 2 |
| Web Search Agent | agents/websearch_agent.py | ⏳ Week 3 |
| Critic Agent | agents/critic_agent.py | ⏳ Week 3 |

### Tech Stack
- LLM: Gemini 1.5 Pro (via langchain-google-genai)
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
│   ├── orchestrator.py
│   ├── arxiv_agent.py
│   ├── graphrag_agent.py
│   ├── websearch_agent.py
│   └── critic_agent.py
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

## ✅ Week 1 Progress

### Completed
- [x] Folder structure created
- [x] Virtual environment set up (python3 -m venv venv)
- [x] requirements.txt installed
- [x] .env + config.py with validation
- [x] ArXiv fetcher (searches + downloads PDFs)
- [x] Neo4j running in Docker
- [x] Neo4j connection manager + schema
- [x] Neo4j ingestor (MERGE-based, idempotent)
- [x] End-to-end pipeline test passed

### Remaining Week 1
- [x] pdf_parser.py ✅
- [x] Week 1 fully complete

---

## ⚙️ Environment Details

### Running Services
- Neo4j: Docker container named 'researchpilot-neo4j'
  - Browser UI: http://localhost:7474
  - Bolt port: bolt://localhost:7687
  - Username: neo4j
  - Password: researchpilot123

### Start Commands (if services are stopped)
```bash
# Start Neo4j
docker start researchpilot-neo4j

# Activate virtual environment
cd /mnt/c/Users/aryan/Documents/researchpilot
source venv/bin/activate
```

### Key Decisions Made
1. Gemini 1.5 Pro instead of Claude (user's API key)
2. MERGE not CREATE in Cypher (idempotency)
3. Dependency injection in Neo4jIngestor
4. Logging over print() throughout
5. Dataclass for Paper object
6. Gradio over CSS/JS (AI/ML engineer context)

---

## 📦 Key Files Content

### config.py
# config.py

from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-lite"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "researchpilot-ai")

APP_ENV = os.getenv("APP_ENV", "development")
MAX_PAPERS_PER_SEARCH = int(os.getenv("MAX_PAPERS_PER_SEARCH", "10"))
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "data/pdfs/")
REPORT_STORAGE_PATH = os.getenv("REPORT_STORAGE_PATH", "reports/")

REQUIRED_KEYS = {
    "GOOGLE_API_KEY": GOOGLE_API_KEY,
    "NEO4J_PASSWORD": NEO4J_PASSWORD,
    "TAVILY_API_KEY": TAVILY_API_KEY,
}

for key_name, key_value in REQUIRED_KEYS.items():
    if not key_value:
        raise ValueError(
            f"❌ Missing required environment variable: {key_name}\n"
            f"   Add it to your .env file and restart."
        )

print("✅ Config loaded successfully")

Searched for regex `def |class ` (`**/pipeline/arxiv_fetcher.py`), 18 results

Searched for regex `def |class ` (`**/pipeline/neo4j_ingestor.py`), 18 results

Searched for regex `def |class ` (`**/graph/connection.py`), 8 results

Here are the created files and all their class and function signatures, with a brief note on their use:

---

### arxiv_fetcher.py

- **class Paper:**
  - Represents a research paper (metadata, local path, etc.).

- **class ArXivFetcher:**
  - Main class for searching and downloading papers from ArXiv.

  - `def __init__(self, storage_path: str = PDF_STORAGE_PATH):`
    - Initializes the fetcher with a storage path for PDFs.

  - `def search_papers(self, query: str, max_results: int = 10) -> List[Paper]:`
    - Searches ArXiv for papers matching a query.

  - `def download_pdf(self, paper: Paper) -> Optional[str]:`
    - Downloads the PDF for a given paper.

  - `def fetch_and_download(self, query: str, max_results: int = 10) -> List[Paper]:`
    - Searches and downloads papers in one step.

---

### neo4j_ingestor.py

- **class Neo4jIngestor:**
  - Handles ingesting paper data into the Neo4j graph database.

  - `def __init__(self, connection: Neo4jConnection):`
    - Initializes with a Neo4j connection.

  - `def ingest_paper(self, paper: Paper) -> bool:`
    - Ingests a single paper into the graph.

  - `def _create_paper_node(self, paper: Paper):`
    - Creates a node for a paper.

  - `def _create_author_relationship(self, paper_id: str, author_name: str):`
    - Links an author to a paper.

  - `def add_concept_to_paper(self, paper_id: str, concept_name: str):`
    - Adds a concept node and links it to a paper.

  - `def link_related_concepts(self, concept_a: str, concept_b: str):`
    - Links two related concepts.

  - `def ingest_papers(self, papers: List[Paper]) -> dict:`
    - Ingests multiple papers at once.

  - `def get_graph_stats(self) -> dict:`
    - Returns statistics about the graph.

---

### connection.py

- **class Neo4jConnection:**
  - Manages the connection to the Neo4j database (singleton-like).

  - `def __init__(self, uri: str, user: str, password: str):`
    - Initializes the connection.

  - `def connect(self):`
    - Establishes the connection.

  - `def get_session(self):`
    - Returns a session for running queries.

  - `def run_query(self, query: str, parameters: dict = None):`
    - Runs a Cypher query.

  - `def close(self):`
    - Closes the connection.

- **def create_schema(conn: Neo4jConnection):**
  - Creates the required schema in the Neo4j database.


---

## 🔜 Next Steps
Currently on: Week 2 — Building the 5 agents with LangGraph
First agent: arxiv_agent.py

---

## 💼 Interview Concepts Covered So Far
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