import json
import subprocess
import sys
from pathlib import Path


FIXTURE = Path("tests/fixtures/v2_local_demo.c")
ABI_FIXTURE = Path("tests/fixtures/v3_abi_demo.c")


def test_cli_json_analyzes_local_c_file():
    result = subprocess.run(
        [sys.executable, "python/cli.py", str(FIXTURE), "--platform", "x86_64", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    structs = {item["name"]: item for item in payload["structs"]}
    assert "TelemetryPacket" in structs
    assert structs["TelemetryPacket"]["analysis"]["waste_bytes"] > 0
    assert structs["TelemetryPacket"]["layout"]["total_size"] == 40
    assert structs["CacheSplitDemo"]["analysis"]["cache_line_splits"]


def test_cli_table_can_filter_struct_by_name():
    result = subprocess.run(
        [
            sys.executable,
            "python/cli.py",
            str(FIXTURE),
            "--platform",
            "x86_64",
            "--struct",
            "TelemetryPacket",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "StructScope CLI" in result.stdout
    assert "TelemetryPacket" in result.stdout
    assert "CompactPacket" not in result.stdout


def test_cli_rules_only_outputs_guidance():
    result = subprocess.run(
        [
            sys.executable,
            "python/cli.py",
            str(FIXTURE),
            "--platform",
            "x86_64",
            "--struct",
            "TelemetryPacket",
            "--rules-only",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "StructScope rules" in result.stdout
    assert "padding.high_waste" in result.stdout
    assert "auto" not in result.stderr.lower()


def test_cli_compare_outputs_platform_summary():
    result = subprocess.run(
        [
            sys.executable,
            "python/cli.py",
            str(FIXTURE),
            "--compare",
            "x86_64",
            "arm32",
            "--struct",
            "TelemetryPacket",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "platform comparison" in result.stdout
    assert "x86_64" in result.stdout
    assert "arm32" in result.stdout


def test_cli_compare_shows_windows_llp64_difference_for_long():
    result = subprocess.run(
        [
            sys.executable,
            "python/cli.py",
            str(ABI_FIXTURE),
            "--compare",
            "x86_64",
            "x86_64_windows",
            "--struct",
            "AbiLongDemo",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "x86_64_windows" in result.stdout
    assert "AbiLongDemo" in result.stdout
    assert "min=" in result.stdout and "max=" in result.stdout


def test_cli_markdown_report_contains_guidance():
    result = subprocess.run(
        [
            sys.executable,
            "python/cli.py",
            str(FIXTURE),
            "--platform",
            "x86_64",
            "--struct",
            "TelemetryPacket",
            "--markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# StructScope Report" in result.stdout
    assert "Rule-based guidance" in result.stdout


def test_cli_fails_fast_for_unresolved_types(tmp_path):
    source = tmp_path / "bad.c"
    source.write_text("struct Bad { MissingType value; int count; };", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "python/cli.py", str(source), "--platform", "x86_64"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Exact layout unavailable" in result.stderr


def test_cli_allow_incomplete_outputs_partial_json(tmp_path):
    source = tmp_path / "bad.c"
    source.write_text("struct Bad { MissingType value; int count; };", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "python/cli.py", str(source), "--platform", "x86_64", "--allow-incomplete", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["layout_complete"] is False
    assert payload["structs"][0]["analysis"]["layout_complete"] is False
