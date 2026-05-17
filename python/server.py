"""Newline-delimited JSON-RPC server for StructScope."""

from __future__ import annotations

import json
import re
import sys
import traceback
from typing import Any

from analyser import analyse
from layout_engine import compute_layout
from parser_c import parse_structs
from parser_rust import parse_structs_rust
from platforms import PLATFORMS, detect_host_platform, detect_host_platform_info, get_platform


RUST_FIXED = {
    "bool": (1, 1),
    "char": (4, 4),
    "i8": (1, 1),
    "u8": (1, 1),
    "i16": (2, 2),
    "u16": (2, 2),
    "i32": (4, 4),
    "u32": (4, 4),
    "f32": (4, 4),
    "i64": (8, 8),
    "u64": (8, 8),
    "f64": (8, 8),
    "i128": (16, 16),
    "u128": (16, 16),
}
QUALIFIERS = {
    "const",
    "volatile",
    "restrict",
    "__restrict",
    "__restrict__",
    "mutable",
    "static",
    "register",
}


class IncompleteLayoutError(ValueError):
    """Raised when an exact layout would require unsupported type information."""


def _normalise_type(raw_type: str) -> str:
    collapsed = " ".join(str(raw_type).replace("\n", " ").replace("\t", " ").split())
    tokens = [token for token in collapsed.split(" ") if token not in QUALIFIERS]
    return " ".join(tokens).strip()


def _split_array(raw_type: str) -> tuple[str, int]:
    text = _normalise_type(raw_type)
    multiplier = 1
    while True:
        match = re.search(r"\[(\d+)\]\s*$", text)
        if not match:
            return text, multiplier
        multiplier *= max(1, int(match.group(1)))
        text = text[: match.start()].strip()


def _split_rust_array(raw_type: str) -> tuple[str, int]:
    text = _normalise_type(raw_type)
    match = re.fullmatch(r"\[\s*(.+?)\s*;\s*(\d+)\s*\]", text)
    if not match:
        return text, 1
    return match.group(1).strip(), max(1, int(match.group(2)))


def _resolve_c(raw_type: str, platform: dict, registry: dict[str, dict[str, int]]) -> tuple[int, int, bool]:
    base, array_len = _split_array(raw_type)
    sizes = platform["type_sizes"]
    alignments = platform["type_alignments"]

    if "*" in base:
        return int(sizes["pointer"]) * array_len, int(alignments["pointer"]), False

    lookup = _normalise_type(base)
    if lookup.startswith("struct "):
        lookup_name = lookup.split(" ", 1)[1]
    elif lookup.startswith("class "):
        lookup_name = lookup.split(" ", 1)[1]
    else:
        lookup_name = lookup

    if lookup in sizes:
        return int(sizes[lookup]) * array_len, int(alignments[lookup]), False
    if lookup_name in registry:
        known = registry[lookup_name]
        return int(known["size"]) * array_len, int(known["alignment"]), False
    return 0, 0, True


def _resolve_rust(raw_type: str, platform: dict, registry: dict[str, dict[str, int]]) -> tuple[int, int, bool]:
    raw, array_len = _split_rust_array(raw_type)
    sizes = platform["type_sizes"]
    alignments = platform["type_alignments"]

    if raw.startswith("&") or raw.startswith("*"):
        return int(sizes["pointer"]) * array_len, int(alignments["pointer"]), False
    if raw in {"usize", "isize"}:
        return int(sizes["pointer"]) * array_len, int(alignments["pointer"]), False
    if raw in RUST_FIXED:
        return RUST_FIXED[raw][0] * array_len, RUST_FIXED[raw][1], False
    if raw in registry:
        known = registry[raw]
        return int(known["size"]) * array_len, int(known["alignment"]), False
    return 0, 0, True


def _retarget_structs(structs: list[dict], platform: dict, language: str) -> list[dict]:
    registry: dict[str, dict[str, int]] = {}
    retargeted = []

    for struct in structs:
        fields = []
        for field in struct.get("fields", []):
            raw_type = str(field.get("raw_type") or field.get("type") or "")
            if language == "rust":
                size, alignment, unresolved = _resolve_rust(raw_type, platform, registry)
            else:
                size, alignment, unresolved = _resolve_c(raw_type, platform, registry)

            adjusted = dict(field)
            adjusted["size"] = size
            adjusted["alignment"] = alignment
            if unresolved:
                adjusted["unresolved"] = True
            else:
                adjusted.pop("unresolved", None)
            fields.append(adjusted)

        layout = compute_layout(fields, platform)
        registry[str(struct.get("name", ""))] = {
            "size": int(layout["total_size"]),
            "alignment": int(layout["alignment"]),
        }
        retargeted.append({**struct, "fields": fields, "layout": layout})

    return retargeted


def _source_model(source: str) -> dict[str, Any]:
    includes = re.findall(r"^\s*#\s*include\s+([<\"].+[>\"])", source, flags=re.MULTILINE)
    return {
        "mode": "single-source-text",
        "preprocessor": False,
        "include_count": len(includes),
        "includes": includes[:20],
        "caveats": [
            "StructScope does not run the C/C++ preprocessor.",
            "Include files, macros, conditional compilation, and cross-translation-unit symbols must be present in the analyzed text or represented by supported primitive types.",
            "Auto platform detection reports the host Python ABI, not a cross-compiler target.",
        ],
    }


def _layout_blockers(structs: list[dict]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for struct in structs:
        struct_name = str(struct.get("name") or "anonymous")
        for field in struct.get("fields", []):
            field_name = str(field.get("name") or "")
            raw_type = str(field.get("raw_type") or field.get("type") or "")
            if field.get("unresolved"):
                blockers.append(
                    {
                        "kind": "unresolved_type",
                        "struct": struct_name,
                        "field": field_name,
                        "type": raw_type,
                        "line": field.get("line"),
                        "message": f"{struct_name}.{field_name} has unresolved type '{raw_type}'",
                    }
                )
            if "bit_width" in field:
                blockers.append(
                    {
                        "kind": "bit_field",
                        "struct": struct_name,
                        "field": field_name,
                        "type": raw_type,
                        "bit_width": field.get("bit_width"),
                        "line": field.get("line"),
                        "message": f"{struct_name}.{field_name} is a bit-field; compiler-specific packing is not modeled",
                    }
                )
    return blockers


def _blockers_for_struct(blockers: list[dict[str, Any]], struct_name: str) -> list[dict[str, Any]]:
    return [blocker for blocker in blockers if blocker.get("struct") == struct_name]


def _raise_for_blockers(blockers: list[dict[str, Any]]) -> None:
    sample = "; ".join(str(blocker["message"]) for blocker in blockers[:5])
    suffix = f" ({len(blockers) - 5} more)" if len(blockers) > 5 else ""
    raise IncompleteLayoutError(
        "Exact layout unavailable: "
        + sample
        + suffix
        + ". Add missing type definitions or pass allow_incomplete=true to inspect a non-authoritative partial result."
    )


def analyse_source(
    source: str,
    language: str,
    platform_name: str = "x86_64",
    cache_line: int = 64,
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    requested_platform = platform_name or "x86_64"
    actual_platform = detect_host_platform() if requested_platform == "auto" else requested_platform
    platform = get_platform(actual_platform)

    if language in {"c", "cpp"}:
        parsed = parse_structs(source, language)
    elif language == "rust":
        parsed = parse_structs_rust(source)
    else:
        raise ValueError("language must be one of: c, cpp, rust")

    retargeted = _retarget_structs(parsed, platform, language)
    blockers = _layout_blockers(retargeted)
    if blockers and not allow_incomplete:
        _raise_for_blockers(blockers)

    response_structs = []
    for struct in retargeted:
        layout = struct["layout"]
        struct_name = str(struct.get("name") or "anonymous")
        struct_blockers = _blockers_for_struct(blockers, struct_name)
        layout = {
            **layout,
            "complete": not struct_blockers,
            "blockers": struct_blockers,
        }
        analysis = analyse(layout, actual_platform, cache_line)
        analysis["layout_complete"] = not struct_blockers
        analysis["blockers"] = struct_blockers
        response_structs.append(
            {
                "name": struct.get("name"),
                "line": struct.get("line"),
                "fields": struct.get("fields", []),
                "layout": layout,
                "analysis": analysis,
            }
        )
    return {
        "structs": response_structs,
        "platform": actual_platform,
        "requested_platform": requested_platform,
        "cache_line": cache_line,
        "source_model": _source_model(source),
        "layout_complete": not blockers,
        "blockers": blockers,
        "allow_incomplete": allow_incomplete,
    }


def compare_platforms(
    source: str,
    language: str,
    platforms: list[str] | None = None,
    cache_line: int = 64,
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    requested = platforms or list(PLATFORMS.keys())
    comparisons = [analyse_source(source, language, platform, cache_line, allow_incomplete) for platform in requested]
    summary: dict[str, dict[str, Any]] = {}

    for comparison in comparisons:
        platform_name = str(comparison.get("platform"))
        for struct in comparison.get("structs", []):
            name = str(struct.get("name"))
            total_size = int(struct["layout"]["total_size"])
            waste = int(struct["analysis"]["waste_bytes"])
            entry = summary.setdefault(
                name,
                {
                    "min_size": total_size,
                    "max_size": total_size,
                    "best_platforms": [],
                    "worst_platforms": [],
                    "by_platform": {},
                },
            )
            entry["min_size"] = min(int(entry["min_size"]), total_size)
            entry["max_size"] = max(int(entry["max_size"]), total_size)
            entry["by_platform"][platform_name] = {
                "total_size": total_size,
                "waste_bytes": waste,
                "grade": struct["analysis"].get("layout_grade"),
            }

    for entry in summary.values():
        min_size = int(entry["min_size"])
        max_size = int(entry["max_size"])
        entry["best_platforms"] = [
            platform for platform, values in entry["by_platform"].items() if values["total_size"] == min_size
        ]
        entry["worst_platforms"] = [
            platform for platform, values in entry["by_platform"].items() if values["total_size"] == max_size
        ]

    return {
        "platforms": requested,
        "cache_line": cache_line,
        "comparisons": comparisons,
        "summary": summary,
    }


def _analyse_request(payload: dict[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "")
    language = str(payload.get("language") or "c")
    platform_name = str(payload.get("platform") or "x86_64")
    cache_line = int(payload.get("cache_line") or 64)
    allow_incomplete = bool(payload.get("allow_incomplete") or False)
    return analyse_source(source, language, platform_name, cache_line, allow_incomplete)


def _compare_request(payload: dict[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "")
    language = str(payload.get("language") or "c")
    platforms = payload.get("platforms")
    cache_line = int(payload.get("cache_line") or 64)
    allow_incomplete = bool(payload.get("allow_incomplete") or False)
    if platforms is not None and not isinstance(platforms, list):
        raise ValueError("platforms must be a list of platform names")
    return compare_platforms(source, language, platforms, cache_line, allow_incomplete)


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    if method == "ping":
        return {"pong": True}
    if method == "platforms":
        return {"platforms": list(PLATFORMS.keys())}
    if method == "detect_platform":
        return detect_host_platform_info()
    if method == "analyse":
        return _analyse_request(request)
    if method == "compare_platforms":
        return _compare_request(request)
    raise ValueError(f"Unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except Exception as exc:  # Keep the server alive on malformed requests.
            if "--debug" in sys.argv:
                traceback.print_exc(file=sys.stderr)
            response = {"error": str(exc)}
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
