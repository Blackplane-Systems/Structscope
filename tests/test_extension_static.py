import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_extension_wires_save_selection_and_backend_recovery_paths():
    source = (ROOT / "src" / "extension.ts").read_text(encoding="utf-8")
    assert "onDidSaveTextDocument" in source
    assert "onDidChangeTextEditorSelection" in source
    assert "restart()" in source
    assert "requestTimeoutMs" in source
    assert "allow_incomplete" in source
    assert "ensurePythonDependencies" in source
    assert "autoInstallPythonDeps" in source


def test_extension_exposes_terminal_and_top_panel_commands():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    commands = {entry["command"] for entry in package["contributes"]["commands"]}
    assert {
        "structscope.analyzeStruct",
        "structscope.openPanel",
        "structscope.runCliInTerminal",
        "structscope.copyAnalysisJson",
        "structscope.showOutput",
    }.issubset(commands)
    assert "editor/title" in package["contributes"]["menus"]
    assert "editor/context" in package["contributes"]["menus"]
    assert "view/title" in package["contributes"]["menus"]
    assert package["contributes"]["viewsContainers"]["activitybar"][0]["id"] == "structscope"


def test_manifest_keeps_runtime_settings_and_lazy_activation():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    activation = set(package["activationEvents"])
    assert "onView:structscope.dashboard" in activation
    assert "onCommand:structscope.analyzeStruct" in activation

    settings = package["contributes"]["configuration"]["properties"]
    for key in [
        "structscope.defaultPlatform",
        "structscope.cacheLine",
        "structscope.analyzeOnSave",
        "structscope.autoOpenPanel",
        "structscope.allowIncompleteLayouts",
        "structscope.requestTimeoutMs",
        "structscope.autoInstallPythonDeps",
    ]:
        assert key in settings
    assert "x86_64_windows" in settings["structscope.defaultPlatform"]["enum"]
    assert "riscv64" in settings["structscope.defaultPlatform"]["enum"]


def test_package_and_lock_versions_match_release():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert package["version"] == "3.1.2"
    assert lock["version"] == package["version"]
    assert lock["packages"][""]["version"] == package["version"]


def test_webview_exposes_easy_access_controls():
    html = (ROOT / "webview" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "webview" / "byteMap.js").read_text(encoding="utf-8")
    assert 'id="analyze-active"' in html
    assert "x86_64_windows" in html
    assert "arm64_windows" in html
    assert "analyze-active" in js
