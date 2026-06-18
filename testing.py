# import logging
# logging.basicConfig(level=logging.INFO)

# from pipeline.arxiv_fetcher import ArXivFetcher
# from agents.graphrag_agent import run_graphrag_agent

# fetcher = ArXivFetcher()

# papers = fetcher.fetch_and_download(
#     "attention mechanism self-supervised learning",
#     max_results=2
# )

# papers_as_dicts = [
#     {
#         "paper_id": p.paper_id,
#         "title": p.title,
#         "local_pdf_path": p.local_pdf_path
#     }
#     for p in papers
# ]

# result = run_graphrag_agent(papers_as_dicts)

# print()
# print("=== GRAPHRAG AGENT RESULT ===")
# print(f"Status          : {result['status']}")
# print(f"Papers processed: {result['processed']}")
# print(f"Errors          : {result['errors']}")
# for p in result['papers']:
#     print(f"\n  Paper: {p['paper_id']}")
#     print(f"  Concepts: {p['concepts']}")



# from agents.websearch_agent import run_websearch_agent
# result = run_websearch_agent('attention mechanism in transformers', max_results=3)
# print('Status:', result['status'])
# print('Findings:', len(result['findings']))
# print('Summary:', result['overall_summary'][:200])

# from langchain_tavily import TavilySearch

# tool = TavilySearch(max_results=3)
# raw = tool.invoke("attention mechanism in transformers")
# print(type(raw))
# print(type(raw[0]) if isinstance(raw, list) else "not a list")
# print(raw[0] if isinstance(raw, list) else raw[:500])

# from langchain_tavily import TavilySearch

# tool = TavilySearch(max_results=3)
# raw = tool.invoke("attention mechanism in transformers")
# print(type(raw))
# print(raw.keys())
# print(raw)  # just print the whole thing — it'll be small enough to read


# testing.py
# Full pipeline test — runs all stages and prints a detailed report

import logging
import sys

# ── Setup logging so we can see what each agent is doing ──────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("arxiv").setLevel(logging.WARNING)

from agents.orchestrator import run_pipeline

# ── Test Query ────────────────────────────────────────────────────────
QUERY = "attention mechanism in transformers"
MAX_PAPERS = 2   # keep low for testing — faster + fewer API calls

print("\n" + "="*60)
print(f"  ResearchPilot Full Pipeline Test")
print(f"  Query: '{QUERY}'")
print(f"  Max papers: {MAX_PAPERS}")
print("="*60 + "\n")

# ── Run the pipeline ──────────────────────────────────────────────────
try:
    report = run_pipeline(QUERY, max_papers=MAX_PAPERS)

    print("\n" + "="*60)
    print("  FINAL REPORT")
    print("="*60)
    print(report)

    print("\n" + "="*60)
    print("  ✅ Pipeline completed successfully")
    print("="*60)

except Exception as e:
    print(f"\n❌ Pipeline crashed with unhandled exception: {e}")
    logging.exception("Full traceback:")
    sys.exit(1)


# Add to testing.py temporarily

# from agents.critic_agent import run_critic_agent

# sample_report = """
# # ResearchPilot Report
# Query: attention mechanism in transformers
# Papers found: 2
# Research gaps: positional encoding alternatives
# Hub concepts: self-attention, multi-head attention
# Web findings: 3 sources covering scaled dot-product attention
# """

# critique = run_critic_agent("attention mechanism in transformers", sample_report)
# print("Status:", critique["status"])
# print("Score:", critique["overall_score"], "/100")
# print("Verdict:", critique["verdict"])
# print("Strengths:", critique["strengths"])
# print("Weaknesses:", critique["weaknesses"])