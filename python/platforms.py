"""Platform ABI tables used by StructScope's static layout engine."""

from __future__ import annotations

from copy import deepcopy
import platform as host_platform
import sys


def _with_aliases(type_sizes: dict[str, int], type_alignments: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    aliases = {
        "signed char": "char",
        "unsigned char": "char",
        "bool": "char",
        "_Bool": "char",
        "signed short": "short",
        "unsigned short": "short",
        "short int": "short",
        "signed short int": "short",
        "unsigned short int": "short",
        "signed int": "int",
        "unsigned int": "int",
        "unsigned": "int",
        "signed": "int",
        "signed long": "long",
        "unsigned long": "long",
        "long int": "long",
        "signed long int": "long",
        "unsigned long int": "long",
        "signed long long": "long long",
        "unsigned long long": "long long",
        "long long int": "long long",
        "signed long long int": "long long",
        "unsigned long long int": "long long",
        "size_t": "pointer",
        "intptr_t": "pointer",
        "uintptr_t": "pointer",
        "ptrdiff_t": "pointer",
        "int8_t": "char",
        "uint8_t": "char",
        "int16_t": "short",
        "uint16_t": "short",
        "int32_t": "int",
        "uint32_t": "int",
        "int64_t": "long long",
        "uint64_t": "long long",
    }
    for alias, target in aliases.items():
        type_sizes[alias] = type_sizes[target]
        type_alignments[alias] = type_alignments[target]
    return type_sizes, type_alignments


def _platform(
    pointer_size: int,
    max_align: int,
    sizes: dict[str, int],
    alignments: dict[str, int],
    *,
    abi: str,
    target_os: str,
    description: str,
) -> dict[str, object]:
    type_sizes, type_alignments = _with_aliases(dict(sizes), dict(alignments))
    return {
        "pointer_size": pointer_size,
        "max_align": max_align,
        "type_sizes": type_sizes,
        "type_alignments": type_alignments,
        "abi": abi,
        "target_os": target_os,
        "description": description,
    }


PLATFORMS: dict[str, dict[str, object]] = {
    "x86_64": _platform(
        pointer_size=8,
        max_align=8,
        abi="LP64",
        target_os="unix",
        description="x86_64 System V / Unix-like LP64 ABI",
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
    ),
    "x86_64_windows": _platform(
        pointer_size=8,
        max_align=8,
        abi="LLP64",
        target_os="windows",
        description="Windows x64 MSVC-compatible LLP64 ABI",
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
    ),
    "arm64": _platform(
        pointer_size=8,
        max_align=8,
        abi="LP64",
        target_os="unix",
        description="AArch64 Unix-like LP64 ABI",
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
    ),
    "arm64_windows": _platform(
        pointer_size=8,
        max_align=8,
        abi="LLP64",
        target_os="windows",
        description="Windows Arm64 MSVC-compatible LLP64 ABI",
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
    ),
    "arm32": _platform(
        pointer_size=4,
        max_align=8,
        abi="ILP32",
        target_os="generic",
        description="32-bit ARM ILP32 ABI",
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
    ),
    "avr": _platform(
        pointer_size=2,
        max_align=1,
        abi="AVR",
        target_os="embedded",
        description="AVR embedded ABI with byte alignment",
        sizes={
            "char": 1,
            "short": 2,
            "int": 2,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 4,
            "pointer": 2,
        },
        alignments={
            "char": 1,
            "short": 1,
            "int": 1,
            "long": 1,
            "long long": 1,
            "float": 1,
            "double": 1,
            "pointer": 1,
        },
    ),
    "riscv32": _platform(
        pointer_size=4,
        max_align=8,
        abi="ILP32",
        target_os="generic",
        description="RISC-V 32-bit ILP32 ABI",
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
    ),
    "riscv64": _platform(
        pointer_size=8,
        max_align=8,
        abi="LP64",
        target_os="generic",
        description="RISC-V 64-bit LP64 ABI",
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
    ),
}


def get_platform(name: str) -> dict[str, object]:
    """Return a defensive copy of an ABI table by name."""

    if name == "auto":
        name = detect_host_platform()
    try:
        return deepcopy(PLATFORMS[name])
    except KeyError as exc:
        known = ", ".join(sorted(PLATFORMS))
        raise ValueError(f"Unknown platform '{name}'. Known platforms: {known}") from exc


def detect_host_platform() -> str:
    """Best-effort host ABI detection for default local analysis.

    This detects the Python host process ABI, not a cross-compiler target.
    Embedded, firmware, and cross-compilation projects should select the
    intended platform explicitly.
    """

    machine = host_platform.machine().lower()
    system = host_platform.system().lower()
    pointer_bits = 64 if sys.maxsize > 2**32 else 32
    if machine in {"x86_64", "amd64"}:
        if system == "windows":
            return "x86_64_windows"
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        if system == "windows":
            return "arm64_windows"
        return "arm64"
    if machine.startswith("arm") or machine.startswith("armv7") or machine.startswith("armv6"):
        return "arm32"
    if "riscv" in machine:
        return "riscv32" if pointer_bits == 32 else "riscv64"
    if system == "windows" and pointer_bits == 64:
        return "x86_64_windows"
    return "x86_64" if pointer_bits == 64 else "arm32"


def detect_host_platform_info() -> dict[str, object]:
    detected = detect_host_platform()
    platform = PLATFORMS[detected]
    return {
        "platform": detected,
        "machine": host_platform.machine(),
        "system": host_platform.system(),
        "pointer_size": platform["pointer_size"],
        "abi": platform["abi"],
        "description": platform["description"],
        "source": "host-python-abi",
        "confidence": "host-only",
        "warning": "Auto-detection reports the host Python ABI. Select an explicit platform for cross-compilers or non-default compiler ABIs.",
    }
