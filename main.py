# main.py
#
# Single entry point for ResearchPilot. Starts the FastAPI backend
# (uvicorn) and the Gradio frontend as two separate processes, waits
# for the API to be ready before declaring success, and shuts both
# down cleanly on Ctrl+C.

import logging
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
API_HOST = "127.0.0.1"
API_PORT = 8000
API_HEALTH_URL = f"http://{API_HOST}:{API_PORT}/health"

STARTUP_TIMEOUT = 30
# Max seconds to wait for the API to report healthy before giving up.
# uvicorn usually boots in 1-2s, but this gives real headroom for a
# slow machine or a cold Neo4j connection on first health check.


def wait_for_api(timeout: int = STARTUP_TIMEOUT) -> bool:
    """
    Polls the API's /health endpoint until it responds or we time out.

    This is the standard pattern for "wait until service X is ready"
    when starting multiple processes together: don't guess with a
    fixed time.sleep(), actually ask the service if it's up. A fixed
    sleep is either too short (flaky) or too long (slow startup) —
    polling adapts to however long the real startup actually takes.
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = requests.get(API_HEALTH_URL, timeout=2)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
            # Connection refused / not listening yet — expected during
            # the first second or two of startup. Not an error, just
            # means "not ready yet, keep polling."

        time.sleep(0.5)

    return False


def main():
    logger.info("=" * 60)
    logger.info("🔬 ResearchPilot AI — starting up")
    logger.info("=" * 60)

    api_process = None
    ui_process = None

    try:
        # ── Start the API ────────────────────────────────────────────
        logger.info(f"🚀 Starting API (uvicorn) on {API_HOST}:{API_PORT}...")
        api_process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "api.routes:app",
                "--host", API_HOST,
                "--port", str(API_PORT),
            ],
            cwd=PROJECT_ROOT,
        )
        # sys.executable — the exact same Python interpreter running
        # main.py right now (i.e. your venv's python.exe). Using this
        # instead of a bare "python" or "uvicorn" string guarantees the
        # subprocess uses the same venv, with the same installed
        # packages, instead of accidentally picking up a different
        # Python on the system PATH.
        #
        # cwd=PROJECT_ROOT — runs the subprocess AS IF you'd typed the
        # command from the project root yourself, regardless of where
        # main.py itself was launched from.

        logger.info("⏳ Waiting for API to become healthy...")
        if not wait_for_api():
            logger.error(
                f"❌ API did not become healthy within {STARTUP_TIMEOUT}s. "
                "Check the uvicorn output above for errors (e.g. Neo4j "
                "not running, config.py validation failure)."
            )
            return
            # return here (not sys.exit or raise) — falls through to
            # the finally block below, which cleans up the API process
            # we already started, instead of leaving it orphaned.

        logger.info("✅ API is healthy")

        # ── Start the UI ─────────────────────────────────────────────
        logger.info("🚀 Starting UI (Gradio)...")
        ui_process = subprocess.Popen(
            [sys.executable, "ui/app.py"],
            cwd=PROJECT_ROOT,
        )

        logger.info("=" * 60)
        logger.info("✅ ResearchPilot is running")
        logger.info(f"   API:  http://{API_HOST}:{API_PORT}/docs")
        logger.info("   UI:   http://127.0.0.1:7860")
        logger.info("   Press Ctrl+C to stop both servers")
        logger.info("=" * 60)

        # ── Keep main.py alive, watch both children ────────────────
        # wait() blocks until ONE of the two processes exits on its
        # own (e.g. crashes). If that happens, we don't want to sit
        # here forever pretending everything's fine — better to stop
        # and report it, then clean up the other process too.
        while True:
            if api_process.poll() is not None:
                logger.error(f"❌ API process exited unexpectedly (code {api_process.returncode})")
                break
            if ui_process.poll() is not None:
                logger.error(f"❌ UI process exited unexpectedly (code {ui_process.returncode})")
                break
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("\n🛑 Shutdown requested (Ctrl+C)")

    finally:
        # This block ALWAYS runs — whether we got here via Ctrl+C,
        # a crashed child process, or the early `return` above after
        # a failed health check. That guarantee is exactly why
        # try/finally is the right tool: cleanup happens no matter
        # which path got us here.
        for name, process in [("UI", ui_process), ("API", api_process)]:
            if process is not None and process.poll() is None:
                # poll() is None means the process is STILL RUNNING.
                # No point calling terminate() on something already dead.
                logger.info(f"   Stopping {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # terminate() asks nicely (SIGTERM); if the process
                    # ignores that for 5s, kill() forces it (SIGKILL).
                    # Without this fallback, a stuck child process could
                    # hang main.py's shutdown indefinitely.
                    logger.warning(f"   {name} did not stop gracefully, forcing kill...")
                    process.kill()

        logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    main()