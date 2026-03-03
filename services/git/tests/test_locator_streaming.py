"""
Tests for the streaming locator analysis endpoint.
Validates that /locators/analyze returns NDJSON with per-file results incrementally.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from locator_scanner import CodeResponse

pytestmark = pytest.mark.asyncio


@pytest.fixture
def setup_repo_with_frontend_files(workspace_dir):
    """Create a fake repo connection + frontend files on disk."""
    import main as git_main

    repo_name = "test-frontend-repo"
    repo_dir = workspace_dir / repo_name / "src" / "pages"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Create small JSX files — some with existing data-testid, some without
    for i in range(5):
        content = (
            f'export default function Page{i}() {{\n'
            f'  return <button data-testid="page{i}-existing-btn">Click {i}</button>;\n'
            f'}}\n'
        ) if i < 2 else (
            f'export default function Page{i}() {{\n'
            f'  return <button>Click {i}</button>;\n'
            f'}}\n'
        )
        (repo_dir / f"Page{i}.jsx").write_text(content, encoding="utf-8")

    conn = git_main.repo_connections_store.create(
        repo_url="https://github.com/acme/test-frontend-repo",
        provider="github",
        repo_path=repo_name,
        auth_type="none",
        repo_type="application_repository",
    )
    yield conn, workspace_dir / repo_name

    try:
        conn_path = git_main.repo_connections_store._path(conn.id)
        if conn_path.exists():
            conn_path.unlink()
    except Exception:
        pass


def _make_mock_update(code_factory):
    """Return an async mock for update_code_with_locators that uses code_factory."""
    async def _mock(code, file_name, *, ollama_url, ollama_model):
        new_code = code_factory(code, file_name)
        return CodeResponse(code=new_code, message=f"Added locators to {file_name}")
    return _mock


async def test_analyze_streams_ndjson(client, setup_repo_with_frontend_files):
    """The endpoint returns NDJSON with metadata, file_result(s), and done events."""
    conn, repo_root = setup_repo_with_frontend_files

    def _add_testid(code, file_name):
        # Simulate adding a data-testid to the button
        return code.replace("<button>", f'<button data-testid="{file_name}-click-btn">')

    with patch("main.update_code_with_locators", new=_make_mock_update(_add_testid)):
        resp = await client.post(
            "/locators/analyze",
            json={"connection_id": conn.id, "path": "src/pages"},
        )

    assert resp.status_code == 200
    assert "application/x-ndjson" in resp.headers.get("content-type", "")

    lines = [json.loads(line) for line in resp.text.strip().split("\n") if line.strip()]

    # First event must be metadata
    assert lines[0]["type"] == "metadata"
    assert lines[0]["total_files"] == 5
    assert lines[0]["connection_id"] == conn.id

    # Last event must be done
    assert lines[-1]["type"] == "done"
    assert lines[-1]["files_scanned"] == 5

    # There should be file_result events
    file_events = [e for e in lines if e["type"] == "file_result"]
    assert len(file_events) == 5

    for ev in file_events:
        assert "file" in ev
        assert "locators" in ev
        assert "previous_locators" in ev
        assert "code" in ev
        assert "message" in ev
        assert ev["files_scanned_so_far"] <= 5


async def test_analyze_404_no_frontend_files(client, setup_repo_with_frontend_files):
    """If the sub-path has no frontend files, should return 404."""
    conn, _ = setup_repo_with_frontend_files
    resp = await client.post(
        "/locators/analyze",
        json={"connection_id": conn.id, "path": "nonexistent"},
    )
    assert resp.status_code == 404


async def test_analyze_detects_previous_locators(client, setup_repo_with_frontend_files):
    """Files that already have data-testid should report them in previous_locators."""
    conn, _ = setup_repo_with_frontend_files

    # Return code unchanged — the mock just passes through
    def _passthrough(code, _file_name):
        return code

    with patch("main.update_code_with_locators", new=_make_mock_update(_passthrough)):
        resp = await client.post(
            "/locators/analyze",
            json={"connection_id": conn.id, "path": "src/pages"},
        )

    lines = [json.loads(l) for l in resp.text.strip().split("\n") if l.strip()]
    file_events = [e for e in lines if e["type"] == "file_result"]

    # Page0 and Page1 have existing data-testid attributes
    files_with_previous = [e for e in file_events if len(e["previous_locators"]) > 0]
    assert len(files_with_previous) == 2

    for ev in files_with_previous:
        assert any("existing-btn" in loc["locator"] for loc in ev["previous_locators"])


async def test_analyze_adds_new_locators(client, setup_repo_with_frontend_files):
    """New data-testid attributes added by the LLM should appear in locators."""
    conn, _ = setup_repo_with_frontend_files

    def _add_testid(code, file_name):
        return code.replace("<button>", f'<button data-testid="{file_name}-click-btn">')

    with patch("main.update_code_with_locators", new=_make_mock_update(_add_testid)):
        resp = await client.post(
            "/locators/analyze",
            json={"connection_id": conn.id, "path": "src/pages"},
        )

    lines = [json.loads(l) for l in resp.text.strip().split("\n") if l.strip()]
    file_events = [e for e in lines if e["type"] == "file_result"]
    done_event = [e for e in lines if e["type"] == "done"][0]

    # All 5 files should have locators (2 files had existing + get new ones kept,
    # 3 files had none and now get one new each)
    total_locators = sum(len(e["locators"]) for e in file_events)
    assert total_locators >= 5  # at least one per file
    assert done_event["total_locators"] == total_locators


async def test_extract_locators_endpoint(client):
    """POST /locators/extract should parse data-testid from HTML code."""
    code = '<div><button data-testid="my-btn">OK</button><input data-testid="my-input" /></div>'
    resp = await client.post("/locators/extract", json={"code": code})
    assert resp.status_code == 200
    data = resp.json()
    locators = data["locators"]
    assert len(locators) == 2
    ids = {l["locator"] for l in locators}
    assert ids == {"my-btn", "my-input"}


async def test_analyze_selected_files_only(client, setup_repo_with_frontend_files):
    """When `files` is provided, only those specific files should be analyzed."""
    conn, _ = setup_repo_with_frontend_files

    def _passthrough(code, _file_name):
        return code

    # Only request analysis for Page0.jsx and Page2.jsx
    selected = ["src/pages/Page0.jsx", "src/pages/Page2.jsx"]

    with patch("main.update_code_with_locators", new=_make_mock_update(_passthrough)):
        resp = await client.post(
            "/locators/analyze",
            json={"connection_id": conn.id, "files": selected},
        )

    lines = [json.loads(l) for l in resp.text.strip().split("\n") if l.strip()]

    assert lines[0]["type"] == "metadata"
    assert lines[0]["total_files"] == 2

    file_events = [e for e in lines if e["type"] == "file_result"]
    assert len(file_events) == 2
    analyzed_files = {e["file"] for e in file_events}
    assert analyzed_files == {"src/pages/Page0.jsx", "src/pages/Page2.jsx"}

    done = [e for e in lines if e["type"] == "done"][0]
    assert done["files_scanned"] == 2
