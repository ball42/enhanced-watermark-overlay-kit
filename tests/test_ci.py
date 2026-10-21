"""CI runs both test suites on every pull request (Linux only)."""

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "test.yml"


def test_workflow_runs_both_suites_on_pull_requests():
    text = WORKFLOW.read_text()
    assert "pull_request:" in text
    assert "runs-on: ubuntu-latest" in text
    assert "macos" not in text.lower()
    assert "run: uv run pytest" in text  # the app suite
    assert "working-directory: wallrender" in text
    assert "run: uv run --project .. pytest" in text  # wallrender, on the app's Pillow pin
    assert "86e3u984w" in text  # why wallrender does not run on its own Pillow range
