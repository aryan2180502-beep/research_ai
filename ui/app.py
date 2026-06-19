# ui/app.py
#
# Gradio frontend for ResearchPilot. Talks to api/routes.py over
# plain HTTP — this UI does NOT import agents/orchestrator directly.
# That separation means the UI is just one possible client of the
# API; you could swap it for a React app later and nothing about
# the backend would need to change.

import logging

import gradio as gr
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000"
# Hardcoded for now since UI and API run on the same machine during
# development. If you ever deploy these as separate services (e.g.
# API on a server, UI elsewhere), this becomes an environment
# variable instead — same idea as NVIDIA_API_KEY living in .env
# rather than being hardcoded in config.py.

REQUEST_TIMEOUT = 500
# /research can legitimately take 30-60+ seconds (it's a synchronous
# call that runs the ENTIRE pipeline). 120s gives headroom before
# requests.post() gives up and raises a timeout exception.

NEO4J_BROWSER_URL = (
    "http://localhost:7474/browser/?cmd=edit&arg="
    "MATCH%20(n)%20RETURN%20n%20LIMIT%20100"
)
# Pragmatic, documented exception to the "UI only talks to the API"
# rule (see module docstring above). Building a custom graph
# visualization endpoint (e.g. via Pyvis) was the "right" way to do
# this, but for now this link-out gets a real, interactive view of
# the concept graph shipped today instead of left as a TODO.
# Bypasses api/routes.py entirely — the user's own browser talks
# directly to Neo4j Browser, not through this app.


# ── API Client Functions ─────────────────────────────────────────────
# Each function below wraps exactly one API endpoint. Keeping a 1:1
# mapping between "thing the UI can do" and "function that calls the
# API" makes it trivial to find what to change later if a route's
# shape changes — same single-responsibility instinct as your agents/
# folder, just applied to HTTP calls instead of LLM tools.

def call_research_api(query: str, max_papers: int) -> tuple[str, str]:
    """
    Calls POST /research. Returns (report_markdown, status_message)
    as a tuple because the Gradio UI shows both: the full report in
    one box, and a short status/error line in another.
    """
    if not query or len(query.strip()) < 3:
        return "", "⚠️ Please enter a query (at least 3 characters)."

    try:
        response = requests.post(
            f"{API_BASE_URL}/research",
            json={"query": query, "max_papers": max_papers},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        # This is the single most common failure mode for a beginner
        # running this for the first time: forgetting to start
        # uvicorn before starting Gradio. Give a message that
        # actually tells them what to do, not a raw stack trace.
        return "", "❌ Could not connect to the API. Is `uvicorn api.routes:app` running on port 8000?"
    except requests.exceptions.Timeout:
        return "", f"❌ Request timed out after {REQUEST_TIMEOUT}s. The pipeline may still be running server-side."

    if response.status_code != 200:
        # FastAPI's HTTPException responses always have a "detail" key —
        # surface that directly instead of a generic "something broke".
        detail = response.json().get("detail", response.text)
        return "", f"❌ API error ({response.status_code}): {detail}"

    data = response.json()
    status = f"✅ Done — {data['papers_found']} papers found, {data['papers_analyzed']} analyzed."
    if data["errors"]:
        status += f" ⚠️ {len(data['errors'])} non-fatal error(s) — see report for details."

    return data["report_markdown"], status


def fetch_report_list() -> list[str]:
    """
    Calls GET /reports. Returns just the filenames, newest first
    (the API already sorts them), for populating the dropdown.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/reports", timeout=10)
        response.raise_for_status()
        # raise_for_status() turns a 4xx/5xx response into a Python
        # exception, so it falls into the except block below instead
        # of silently returning bad data. Good default any time you
        # don't need to inspect the status code yourself.
        return [r["filename"] for r in response.json()]
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not fetch report list: {e}")
        return []


def fetch_report_content(filename: str) -> str:
    """Calls GET /reports/{filename}. Returns the markdown content."""
    if not filename:
        return "Select a report from the dropdown above."

    try:
        response = requests.get(f"{API_BASE_URL}/reports/{filename}", timeout=10)
        response.raise_for_status()
        return response.json()["content"]
    except requests.exceptions.RequestException as e:
        return f"❌ Could not load report: {e}"


def fetch_graph_stats() -> tuple[str, str]:
    """
    Calls GET /graph/stats AND GET /health. Returns (stats_markdown,
    health_status) — two separate calls because they answer two
    different questions: "what's in the graph" vs "is the system up".
    """
    # Health first — if Neo4j is down, the stats call will fail too,
    # so checking health first gives a clearer error message.
    try:
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        health_data = health_response.json()
        health_status = (
            f"🟢 API healthy — Neo4j connected"
            if health_data["neo4j_connected"]
            else "🟡 API up, but Neo4j is NOT connected — start the Docker container"
        )
    except requests.exceptions.RequestException:
        return "—", "🔴 Cannot reach the API. Is `uvicorn api.routes:app` running?"

    try:
        stats_response = requests.get(f"{API_BASE_URL}/graph/stats", timeout=10)
        stats_response.raise_for_status()
        stats = stats_response.json()
        stats_markdown = (
            f"**Papers:** {stats.get('papers', 0)}\n\n"
            f"**Concepts:** {stats.get('concepts', 0)}\n\n"
            f"**Relationships:** {stats.get('relationships', 0)}"
        )
    except requests.exceptions.RequestException as e:
        stats_markdown = f"Could not load graph stats: {e}"

    return stats_markdown, health_status


# ── Gradio UI Layout ──────────────────────────────────────────────────

with gr.Blocks(title="ResearchPilot AI") as demo:
    gr.Markdown("# 🔬 ResearchPilot AI")
    gr.Markdown(
        "Autonomous research assistant — searches ArXiv, builds a "
        "knowledge graph, and finds research gaps."
    )

    with gr.Tabs():

        # ── Tab 1: Run Research ─────────────────────────────────────
        with gr.Tab("🔍 Run Research"):
            with gr.Row():
                query_input = gr.Textbox(
                    label="Research Query",
                    placeholder="e.g. graph neural networks for drug discovery",
                    scale=3,
                )
                max_papers_input = gr.Slider(
                    label="Max Papers",
                    minimum=1,
                    maximum=10,
                    value=3,
                    step=1,
                    scale=1,
                )

            run_button = gr.Button("Run Pipeline", variant="primary")
            status_output = gr.Markdown()
            # gr.Markdown() for status, not gr.Textbox() — lets the
            # ✅/❌/⚠️ emoji and any markdown formatting render properly
            # instead of showing as raw text.

            report_output = gr.Markdown(label="Report")

            run_button.click(
                fn=call_research_api,
                inputs=[query_input, max_papers_input],
                outputs=[report_output, status_output],
                # The order here MUST match the tuple order returned
                # by call_research_api(): (report_markdown, status).
                # Gradio maps outputs positionally, not by name.
            )

        # ── Tab 2: Past Reports ──────────────────────────────────────
        with gr.Tab("📂 Past Reports"):
            refresh_button = gr.Button("🔄 Refresh List")
            report_dropdown = gr.Dropdown(
                label="Select a saved report",
                choices=[],
                interactive=True,
            )
            report_viewer = gr.Markdown()

            # When the tab's dropdown should populate: on a manual
            # refresh click. We don't auto-load on page load to avoid
            # an API call firing before the user has even seen the UI
            # (and to keep behavior predictable if the API isn't up yet).
            refresh_button.click(
                fn=fetch_report_list,
                outputs=report_dropdown,
            )

            report_dropdown.change(
                fn=fetch_report_content,
                inputs=report_dropdown,
                outputs=report_viewer,
            )

        # ── Tab 3: Graph Stats ───────────────────────────────────────
        with gr.Tab("📊 Graph Stats"):
            stats_refresh_button = gr.Button("🔄 Refresh Stats")
            health_output = gr.Markdown()
            stats_output = gr.Markdown()

            gr.Markdown(
                f"---\n"
                f"### 🕸️ View the Concept Graph\n"
                f"Stats above are counts only. To see the actual graph "
                f"shape — which concepts cluster together, which papers "
                f"connect to what — open it directly in "
                f"[Neo4j Browser]({NEO4J_BROWSER_URL}).\n\n"
                f"*(Requires the Neo4j Docker container to be running. "
                f"Login: `neo4j` / `researchpilot123`.)*"
            )

            stats_refresh_button.click(
                fn=fetch_graph_stats,
                outputs=[stats_output, health_output],
            )

    # Load graph stats once automatically when the UI first opens —
    # this tab is read-only and cheap to call, unlike /research, so
    # auto-loading here is safe and saves a click.
    demo.load(
        fn=fetch_graph_stats,
        outputs=[stats_output, health_output],
    )


if __name__ == "__main__":
    logger.info(f"🚀 Starting Gradio UI — expects API at {API_BASE_URL}")
    demo.launch()