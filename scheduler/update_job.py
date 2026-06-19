# scheduler/update_job.py
#
# Runs the ResearchPilot pipeline on a recurring schedule for a list
# of "watched topics" read from watched_topics.json. Each run produces
# a timestamped markdown report saved to reports/.

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to Python's import search path.
# Without this, running `python scheduler/update_job.py` only adds
# the scheduler/ folder itself to sys.path — not the project root —
# so `from agents.orchestrator import ...` can't find the agents/
# package. This line manually adds the parent folder so the import
# works no matter where you launch the script from.
sys.path.insert(0, str(Path(__file__).parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler

from agents.orchestrator import run_pipeline

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).parent.parent
TOPICS_FILE = PROJECT_ROOT / "watched_topics.json"
REPORTS_DIR = PROJECT_ROOT / "reports"


# ── Helpers ───────────────────────────────────────────────────────────

def load_topics() -> list[str]:
    """
    Reads watched_topics.json and returns the list of query strings.

    Returns an empty list (never crashes) if the file is missing,
    empty, or malformed — same "fail soft" philosophy as the rest
    of the pipeline. A scheduler that crashes on a typo in a JSON
    file is worse than one that just logs a warning and skips a tick.
    """
    if not TOPICS_FILE.exists():
        logger.error(f"Topics file not found: {TOPICS_FILE}")
        return []

    try:
        with open(TOPICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        topics = data.get("topics", [])

        if not topics:
            logger.warning("watched_topics.json has no topics — nothing to run")

        return topics

    except json.JSONDecodeError as e:
        logger.error(f"watched_topics.json is malformed: {e}")
        return []


def save_report(query: str, report: str) -> Path:
    """
    Saves a report as a timestamped markdown file.

    Filename pattern: reports/2026-06-19_14-30-05_graph-neural-networks.md
    The timestamp prefix means files sort chronologically by default
    in any file browser, and you never overwrite a previous run.
    """
    REPORTS_DIR.mkdir(exist_ok=True)
    # exist_ok=True — don't raise an error if reports/ already exists.
    # Without this, the second run of the scheduler would crash.

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Turn the query into a filesystem-safe slug:
    # "graph neural networks!" -> "graph-neural-networks"
    safe_slug = "".join(
        c if c.isalnum() or c == " " else "" for c in query
    ).strip().replace(" ", "-").lower()[:50]
    # [:50] caps the slug length — long queries shouldn't produce
    # filenames so long the filesystem rejects them.

    filename = f"{timestamp}_{safe_slug}.md"
    filepath = REPORTS_DIR / filename

    filepath.write_text(report, encoding="utf-8")
    return filepath


# ── The Job ───────────────────────────────────────────────────────────

def run_all_watched_topics():
    """
    The function APScheduler calls on every tick.

    Loops through every topic in watched_topics.json, runs the full
    pipeline for each, and saves the report. One topic failing does
    NOT stop the others — same graceful-degradation pattern as
    Orchestrator.run(), just applied across topics instead of stages.
    """
    logger.info("=" * 60)
    logger.info("🔄 Scheduled update job starting")

    topics = load_topics()

    if not topics:
        logger.warning("No topics to process — skipping this run")
        return

    logger.info(f"Processing {len(topics)} watched topic(s)")

    for i, query in enumerate(topics, 1):
        logger.info(f"[{i}/{len(topics)}] Running pipeline for: '{query}'")

        try:
            report = run_pipeline(query)
            filepath = save_report(query, report)
            logger.info(f"[{i}/{len(topics)}] ✅ Report saved: {filepath}")

        except Exception as e:
            # This is the critical line. Without this try/except,
            # one bad topic (e.g. ArXiv timeout, Neo4j hiccup) would
            # raise an exception, kill the loop, and silently skip
            # every remaining topic for this entire scheduled run.
            logger.error(f"[{i}/{len(topics)}] ❌ Failed for '{query}': {e}")
            continue
            # continue explicitly moves to the next topic —
            # included for readability even though it's the last
            # line in the loop anyway.

    logger.info("✅ Scheduled update job complete")
    logger.info("=" * 60)


# ── Scheduler Setup ───────────────────────────────────────────────────

def start_scheduler():
    """
    Configures and starts the BlockingScheduler.

    BlockingScheduler takes over the current thread and runs forever
    (until you Ctrl+C). That's correct here because this script's
    ONLY job is to schedule — nothing else needs the main thread.

    Once api/routes.py exists in Week 4 and FastAPI needs the main
    thread for serving requests, this should switch to
    BackgroundScheduler instead, started from within the FastAPI app.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    scheduler = BlockingScheduler()

    scheduler.add_job(
        run_all_watched_topics,
        trigger="interval",
        hours=1,
        id="watched_topics_update",
        next_run_time=datetime.now(),
        # next_run_time=datetime.now() makes it fire IMMEDIATELY on
        # startup, then every hour after that. Without this, you'd
        # wait a full hour before seeing any output — annoying when
        # you're testing whether this even works.
    )

    logger.info("📅 Scheduler starting — running every 1 hour")
    logger.info(f"📂 Watching topics from: {TOPICS_FILE}")
    logger.info(f"📂 Saving reports to: {REPORTS_DIR}")
    logger.info("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n🛑 Scheduler stopped by user")


# ── TEMPORARY: run once and exit ───────────────────────────────────────
# Swap RUN_ONCE between True/False to toggle behavior without deleting
# any code. Currently True for testing — flip back to False (or just
# call start_scheduler() directly) to restore the every-1-hour loop.
RUN_ONCE = True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    if RUN_ONCE:
        logger.info("🔂 RUN_ONCE mode — running the job a single time, no scheduling loop")
        run_all_watched_topics()
        logger.info("✅ Done. Exiting (RUN_ONCE=True). Set RUN_ONCE=False to resume hourly scheduling.")
    else:
        start_scheduler()