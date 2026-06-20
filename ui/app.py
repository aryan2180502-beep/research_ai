# ui/app.py
#
# Gradio frontend for ResearchPilot. Talks to api/routes.py over
# plain HTTP — this UI does NOT import agents/orchestrator directly.
# That separation means the UI is just one possible client of the
# API; you could swap it for a React app later and nothing about
# the backend would need to change.
#
# ARCHITECTURE NOTE (Phase 2g): the "Run Research" tab's PDF download
# panel is a second, documented exception to the "UI only talks to the
# API" rule — same category as NEO4J_BROWSER_URL below. The API returns
# each paper's local_pdf_path as a string in the JSON response; this
# Gradio process then reads that path directly off disk via gr.File()
# rather than the API re-streaming bytes it already has on the same
# machine through a dedicated endpoint. This only works because UI and
# API are co-located in dev. If they ever become separate machines,
# this breaks and needs a real /papers/{id}/pdf streaming endpoint —
# noted here so future-you doesn't have to rediscover that the hard way.

import logging

import gradio as gr
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000"
REQUEST_TIMEOUT = 500

NEO4J_BROWSER_URL = (
    "http://localhost:7474/browser/?cmd=edit&arg="
    "MATCH%20(n)%20RETURN%20n%20LIMIT%20100"
)


# ── API Client Functions ─────────────────────────────────────────────

def _format_papers_panel(paper_analyses: list[dict]) -> str:
    """
    NEW (Phase 2g): renders the right-hand "Actions" panel's text —
    one line per paper with its title and how many concepts were
    extracted from it. Kept deliberately short; the full per-concept
    summaries already live in report_output on the left.
    """
    if not paper_analyses:
        return "_No papers analyzed in this run._"

    lines = ["### 📑 Papers in this run", ""]
    for a in paper_analyses:
        concept_count = len(a.get("concepts", []))
        lines.append(f"- **{a.get('title', 'Untitled')}** — {concept_count} concepts")
    return "\n".join(lines)


def call_research_api(query: str, max_papers: int):
    """
    Calls POST /research. Returns a 4-tuple:
    (report_markdown, status_message, papers_panel_markdown, pdf_paths)

    NEW (Phase 2g): grew from 2 outputs to 4 — the extra two feed the
    right-hand side panel (layout C) that didn't exist before.
    """
    if not query or len(query.strip()) < 3:
        return "", "⚠️ Please enter a query (at least 3 characters).", "", []

    try:
        response = requests.post(
            f"{API_BASE_URL}/research",
            json={"query": query, "max_papers": max_papers},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        return (
            "",
            "❌ Could not connect to the API. Is `uvicorn api.routes:app` running on port 8000?",
            "",
            [],
        )
    except requests.exceptions.Timeout:
        return (
            "",
            f"❌ Request timed out after {REQUEST_TIMEOUT}s. The pipeline may still be running server-side.",
            "",
            [],
        )

    if response.status_code != 200:
        detail = response.json().get("detail", response.text)
        return "", f"❌ API error ({response.status_code}): {detail}", "", []

    data = response.json()
    status = f"✅ Done — {data['papers_found']} papers found, {data['papers_analyzed']} analyzed."
    if data["errors"]:
        status += f" ⚠️ {len(data['errors'])} non-fatal error(s) — see report for details."

    paper_analyses = data.get("paper_analyses", [])
    papers_panel = _format_papers_panel(paper_analyses)
    pdf_paths = [
        a["local_pdf_path"] for a in paper_analyses if a.get("local_pdf_path")
    ]

    return data["report_markdown"], status, papers_panel, pdf_paths


def fetch_report_list() -> list[str]:
    try:
        response = requests.get(f"{API_BASE_URL}/reports", timeout=10)
        response.raise_for_status()
        return [r["filename"] for r in response.json()]
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not fetch report list: {e}")
        return []


def fetch_report_content(filename: str) -> str:
    if not filename:
        return "Select a report from the dropdown above."

    try:
        response = requests.get(f"{API_BASE_URL}/reports/{filename}", timeout=10)
        response.raise_for_status()
        return response.json()["content"]
    except requests.exceptions.RequestException as e:
        return f"❌ Could not load report: {e}"


def fetch_graph_stats() -> tuple[str, str]:
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

        # ── Tab 1: Run Research (Layout C: report left, actions right) ──
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

            with gr.Row():
                with gr.Column(scale=2):
                    report_output = gr.Markdown(label="Report")

                # NEW (Phase 2g): right-hand actions panel — paper list
                # + concept counts, and a multi-file PDF download box.
                with gr.Column(scale=1):
                    gr.Markdown("## ⚡ Actions")
                    papers_panel_output = gr.Markdown()
                    pdf_files_output = gr.File(
                        label="📄 Download Paper PDFs",
                        file_count="multiple",
                        interactive=False,
                        # interactive=False — this box is for the user
                        # to DOWNLOAD files we already have, not upload
                        # new ones. Without this it'd render as an
                        # upload widget, which is the wrong affordance.
                    )

            run_button.click(
                fn=call_research_api,
                inputs=[query_input, max_papers_input],
                outputs=[report_output, status_output, papers_panel_output, pdf_files_output],
                # Order MUST match call_research_api()'s return tuple:
                # (report_markdown, status, papers_panel, pdf_paths)
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

    demo.load(
        fn=fetch_graph_stats,
        outputs=[stats_output, health_output],
    )


if __name__ == "__main__":
    logger.info(f"🚀 Starting Gradio UI — expects API at {API_BASE_URL}")
    demo.launch()