"""Command-line entry point for StructScope analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from server import analyse_source, compare_platforms
from platforms import PLATFORMS


EXTENSION_LANGUAGE = {
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".rs": "rust",
}


def infer_language(path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        return EXTENSION_LANGUAGE[path.suffix.lower()]
    except KeyError as exc:
        raise SystemExit(f"Cannot infer language from '{path.name}'. Use --language c|cpp|rust.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze C, C++, or Rust struct layout locally.")
    parser.add_argument("file", type=Path, help="Source file to analyze")
    parser.add_argument("--language", choices=["c", "cpp", "rust"], help="Override language detection")
    parser.add_argument("--platform", default="auto", help=f"ABI platform: auto or one of {', '.join(sorted(PLATFORMS))}")
    parser.add_argument("--cache-line", type=int, default=64, help="Cache-line size in bytes")
    parser.add_argument("--struct", dest="struct_name", help="Print only one struct by name")
    parser.add_argument("--json", action="store_true", help="Emit full JSON instead of a compact table")
    parser.add_argument("--compare", nargs="*", help="Compare platforms. With no names, compares all platforms.")
    parser.add_argument("--rules-only", action="store_true", help="Print only rule-based guidance")
    parser.add_argument("--markdown", action="store_true", help="Emit a Markdown report")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Return non-authoritative partial layouts for unresolved types or bit-fields instead of failing fast.",
    )
    return parser


def print_table(result: dict, struct_name: str | None) -> None:
    structs = result.get("structs", [])
    if struct_name:
        structs = [item for item in structs if item.get("name") == struct_name]
    if not structs:
        raise SystemExit("No matching structs found.")

    print(f"StructScope CLI | platform={result.get('platform')} cache_line={result.get('cache_line')}B")
    for struct in structs:
        layout = struct["layout"]
        analysis = struct["analysis"]
        print()
        print(
            f"{struct['name']}: total={layout['total_size']}B "
            f"padding={analysis['waste_bytes']}B ({analysis['waste_ratio'] * 100:.1f}%) "
            f"optimal={analysis['optimal_size']}B savings={analysis['savings']}B"
        )
        print("  field                 type                  off   size  pad")
        print("  -------------------------------------------------------------")
        for field in layout["fields"]:
            print(
                f"  {field['name'][:21]:21} "
                f"{(field.get('raw_type') or field.get('type') or '')[:21]:21} "
                f"{field['offset']:>4}  {field['size']:>4}  {field.get('padding_after', 0):>3}"
            )
        for warning in analysis.get("warnings", []):
            print(f"  warning: {warning}")
        for rule in analysis.get("rules", []):
            print(f"  {rule['severity']}: {rule['title']} - {rule['recommendation']}")


def print_rules(result: dict, struct_name: str | None) -> None:
    structs = _filter_structs(result, struct_name)
    if not structs:
        raise SystemExit("No matching structs found.")
    print(f"StructScope rules | platform={result.get('platform')} cache_line={result.get('cache_line')}B")
    for struct in structs:
        analysis = struct["analysis"]
        print()
        print(f"{struct['name']}: grade={analysis.get('layout_grade')} score={analysis.get('layout_score')}")
        for rule in analysis.get("rules", []):
            field_suffix = f" fields={','.join(rule['fields'])}" if rule.get("fields") else ""
            print(f"  [{rule['severity']}] {rule['id']}: {rule['message']}{field_suffix}")
            print(f"      recommendation: {rule['recommendation']}")


def print_markdown(result: dict, struct_name: str | None) -> None:
    structs = _filter_structs(result, struct_name)
    print(f"# StructScope Report\n")
    print(f"- Platform: `{result.get('platform')}`")
    print(f"- Cache line: `{result.get('cache_line')}B`\n")
    for struct in structs:
        layout = struct["layout"]
        analysis = struct["analysis"]
        print(f"## {struct['name']}\n")
        print(f"- Total size: `{layout['total_size']} bytes`")
        print(f"- Padding: `{analysis['waste_bytes']} bytes ({analysis['waste_ratio'] * 100:.1f}%)`")
        print(f"- Optimal size: `{analysis['optimal_size']} bytes`")
        print(f"- Grade: `{analysis.get('layout_grade')}` (`{analysis.get('layout_score')}/100`)\n")
        print("| Field | Type | Offset | Size | Padding after |")
        print("| --- | --- | ---: | ---: | ---: |")
        for field in layout["fields"]:
            print(
                f"| {field['name']} | {field.get('raw_type') or field.get('type') or ''} | "
                f"{field['offset']} | {field['size']} | {field.get('padding_after', 0)} |"
            )
        if analysis.get("rules"):
            print("\n### Rule-based guidance\n")
            for rule in analysis["rules"]:
                print(f"- **{rule['title']}** (`{rule['severity']}`): {rule['recommendation']}")
        print()


def print_compare(result: dict, struct_name: str | None) -> None:
    print(f"StructScope platform comparison | cache_line={result.get('cache_line')}B")
    for name, summary in sorted(result.get("summary", {}).items()):
        if struct_name and name != struct_name:
            continue
        print()
        print(f"{name}: min={summary['min_size']}B max={summary['max_size']}B best={','.join(summary['best_platforms'])}")
        print("  platform    size  waste  grade")
        print("  ------------------------------")
        for platform, values in sorted(summary["by_platform"].items()):
            print(f"  {platform:10} {values['total_size']:>4}  {values['waste_bytes']:>5}  {values['grade']}")


def _filter_structs(result: dict, struct_name: str | None) -> list[dict]:
    structs = result.get("structs", [])
    if struct_name:
        return [item for item in structs if item.get("name") == struct_name]
    return structs


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_path = args.file
    source = source_path.read_text(encoding="utf-8")
    language = infer_language(source_path, args.language)
    if args.compare is not None:
        platforms = args.compare if args.compare else None
        try:
            result = compare_platforms(source, language, platforms, args.cache_line, args.allow_incomplete)
        except ValueError as exc:
            print(f"StructScope error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            json.dump(result, sys.stdout, indent=2)
            print()
        else:
            print_compare(result, args.struct_name)
        return 0

    try:
        result = analyse_source(source, language, args.platform, args.cache_line, args.allow_incomplete)
    except ValueError as exc:
        print(f"StructScope error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        if args.struct_name:
            result = {
                **result,
                "structs": [item for item in result.get("structs", []) if item.get("name") == args.struct_name],
            }
        json.dump(result, sys.stdout, indent=2)
        print()
    elif args.markdown:
        print_markdown(result, args.struct_name)
    elif args.rules_only:
        print_rules(result, args.struct_name)
    else:
        print_table(result, args.struct_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
