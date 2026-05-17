from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_extension_wires_save_selection_and_backend_recovery_paths():
    source = (ROOT / "src" / "extension.ts").read_text(encoding="utf-8")
    assert "onDidSaveTextDocument" in source
    assert "onDidChangeTextEditorSelection" in source
    assert "restart()" in source
    assert "requestTimeoutMs" in source
    assert "allow_incomplete" in source


def test_extension_exposes_terminal_and_top_panel_commands():
    package = (ROOT / "package.json").read_text(encoding="utf-8")
    assert "structscope.runCliInTerminal" in package
    assert '"editor/title"' in package
    assert '"view/title"' in package


def test_webview_exposes_easy_access_controls():
    html = (ROOT / "webview" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "webview" / "byteMap.js").read_text(encoding="utf-8")
    assert 'id="analyze-active"' in html
    assert "x86_64_windows" in html
    assert "arm64_windows" in html
    assert "analyze-active" in js
