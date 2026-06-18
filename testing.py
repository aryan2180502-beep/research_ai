import logging
logging.basicConfig(level=logging.INFO)

from pipeline.arxiv_fetcher import ArXivFetcher
from agents.graphrag_agent import run_graphrag_agent

fetcher = ArXivFetcher()

papers = fetcher.fetch_and_download(
    "attention mechanism self-supervised learning",
    max_results=2
)

papers_as_dicts = [
    {
        "paper_id": p.paper_id,
        "title": p.title,
        "local_pdf_path": p.local_pdf_path
    }
    for p in papers
]

result = run_graphrag_agent(papers_as_dicts)

print()
print("=== GRAPHRAG AGENT RESULT ===")
print(f"Status          : {result['status']}")
print(f"Papers processed: {result['processed']}")
print(f"Errors          : {result['errors']}")
for p in result['papers']:
    print(f"\n  Paper: {p['paper_id']}")
    print(f"  Concepts: {p['concepts']}")