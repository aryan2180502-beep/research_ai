# config.py
# This file is the single source of truth for all configuration.
# Every other file imports from here — nobody touches .env directly.

from dotenv import load_dotenv
import os

# ── Load the .env file ────────────────────────────────────────────────
load_dotenv()
# load_dotenv() finds the .env file and loads all variables into
# Python's environment (os.environ). After this line, os.getenv()
# can access them.

# ── LLM Settings ──────────────────────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"

# ── Neo4j Settings ────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
# The second argument to os.getenv() is a DEFAULT VALUE.
# If NEO4J_URI is not in .env, it falls back to "bolt://localhost:7687"
# NEO4J_PASSWORD has no default — it must be set explicitly.

# ── Tavily Settings ───────────────────────────────────────────────────
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ── LangSmith Settings ────────────────────────────────────────────────
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "researchpilot-ai")

# ── App Settings ──────────────────────────────────────────────────────
APP_ENV = os.getenv("APP_ENV", "development")
MAX_PAPERS_PER_SEARCH = int(os.getenv("MAX_PAPERS_PER_SEARCH", "5"))
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "data/pdfs/")
REPORT_STORAGE_PATH = os.getenv("REPORT_STORAGE_PATH", "reports/")
# int() converts the string "10" from .env into the number 10.
# Everything in .env is a string — you must convert manually.

# ── Validation ────────────────────────────────────────────────────────
# Check that critical keys exist at startup.
# Better to crash immediately with a clear message than to fail
# mysteriously later when an agent tries to use a None key.
REQUIRED_KEYS = {
    "NVIDIA_API_KEY": NVIDIA_API_KEY,
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