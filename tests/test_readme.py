from pathlib import Path


README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_uses_current_package_commands_and_versionless_install_steps():
    text = README.read_text(encoding="utf-8")
    assert "npm install" in text
    assert "npm run package" in text
    assert "pip install -r python/requirements.txt" in text
    assert "\npm install" not in text
    assert "\npx @vscode" not in text
    assert "struct-scope-1.0.2.vsix" not in text


def test_readme_documents_runtime_dependency_bootstrap_and_exactness_limits():
    text = README.read_text(encoding="utf-8")
    assert "structscope.autoInstallPythonDeps" in text
    assert "fail fast" in text
    assert "x86_64_windows" in text
    assert "LLP64" in text
