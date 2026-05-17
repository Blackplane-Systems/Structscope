from platforms import PLATFORMS, detect_host_platform


def test_windows_llp64_tables_keep_long_at_four_bytes():
    assert PLATFORMS["x86_64_windows"]["type_sizes"]["long"] == 4
    assert PLATFORMS["arm64_windows"]["type_sizes"]["long"] == 4
    assert PLATFORMS["x86_64_windows"]["type_sizes"]["pointer"] == 8
    assert PLATFORMS["arm64_windows"]["type_sizes"]["pointer"] == 8
    assert PLATFORMS["x86_64"]["type_sizes"]["long"] == 8
    assert PLATFORMS["arm64"]["type_sizes"]["long"] == 8


def test_auto_detection_distinguishes_windows_x64(monkeypatch):
    monkeypatch.setattr("platforms.host_platform.machine", lambda: "AMD64")
    monkeypatch.setattr("platforms.host_platform.system", lambda: "Windows")
    monkeypatch.setattr("platforms.sys.maxsize", 2**63 - 1)
    assert detect_host_platform() == "x86_64_windows"


def test_auto_detection_handles_riscv64(monkeypatch):
    monkeypatch.setattr("platforms.host_platform.machine", lambda: "riscv64")
    monkeypatch.setattr("platforms.host_platform.system", lambda: "Linux")
    monkeypatch.setattr("platforms.sys.maxsize", 2**63 - 1)
    assert detect_host_platform() == "riscv64"
