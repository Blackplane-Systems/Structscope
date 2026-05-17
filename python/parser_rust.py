"""Tree-sitter based Rust struct extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tree_sitter import Language, Parser

import tree_sitter_rust

from layout_engine import compute_layout
from platforms import PLATFORMS


X86_64 = PLATFORMS["x86_64"]
RUST_PRIMITIVES: dict[str, tuple[int, int]] = {
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
    "usize": (8, 8),
    "isize": (8, 8),
    "i128": (16, 16),
    "u128": (16, 16),
}


@dataclass
class ResolvedType:
    size: int
    alignment: int
    unresolved: bool = False


def _parser() -> Parser:
    parser = Parser()
    parser.language = Language(tree_sitter_rust.language())
    return parser


def _text(node) -> str:
    return node.text.decode("utf-8", errors="replace")


def _walk(node) -> Iterable:
    yield node
    for child in node.children:
        yield from _walk(child)


def _child(node, *types: str):
    for child in node.children:
        if child.type in types:
            return child
    return None


def _normalise_type(raw_type: str) -> str:
    return " ".join(raw_type.replace("\n", " ").replace("\t", " ").split())


def _array_length(type_node) -> int:
    if type_node is None or type_node.type != "array_type":
        return 1
    for node in _walk(type_node):
        if node.type == "integer_literal":
            try:
                return max(1, int(_text(node), 0))
            except ValueError:
                return 1
    return 1


def _inner_array_type(type_node):
    if type_node is None or type_node.type != "array_type":
        return type_node
    named_children = [child for child in type_node.named_children if child.type != "integer_literal"]
    return named_children[0] if named_children else type_node


def _resolve_type(type_node, registry: dict[str, ResolvedType]) -> ResolvedType:
    if type_node is None:
        return ResolvedType(0, 0, unresolved=True)

    if type_node.type in {"reference_type", "pointer_type"}:
        sizes = X86_64["type_sizes"]
        alignments = X86_64["type_alignments"]
        return ResolvedType(int(sizes["pointer"]), int(alignments["pointer"]))

    length = _array_length(type_node)
    lookup_node = _inner_array_type(type_node)
    raw = _normalise_type(_text(lookup_node))

    if raw in RUST_PRIMITIVES:
        size, alignment = RUST_PRIMITIVES[raw]
        return ResolvedType(size * length, alignment)
    if raw in registry:
        known = registry[raw]
        return ResolvedType(known.size * length, known.alignment)
    return ResolvedType(0, 0, unresolved=True)


def _extract_fields(struct_node, registry: dict[str, ResolvedType]) -> list[dict]:
    body = struct_node.child_by_field_name("body") or _child(struct_node, "field_declaration_list")
    if body is None:
        return []

    fields: list[dict] = []
    tuple_index = 0
    for declaration in body.children:
        if declaration.type == "field_declaration":
            name_node = declaration.child_by_field_name("name") or _child(declaration, "field_identifier")
            type_node = declaration.child_by_field_name("type")
            if name_node is None:
                continue
            name = _text(name_node)
        elif declaration.type == "ordered_field_declaration":
            type_node = declaration.child_by_field_name("type") or declaration.named_children[0]
            name = str(tuple_index)
            tuple_index += 1
        else:
            continue

        raw_type = _normalise_type(_text(type_node)) if type_node is not None else ""
        resolved = _resolve_type(type_node, registry)
        field = {
            "name": name,
            "raw_type": raw_type,
            "type": raw_type,
            "size": resolved.size,
            "alignment": resolved.alignment,
            "line": declaration.start_point[0] + 1,
        }
        if resolved.unresolved:
            field["unresolved"] = True
        fields.append(field)

    return fields


def parse_structs_rust(source: str) -> list[dict]:
    parser = _parser()
    tree = parser.parse(source.encode("utf-8"))
    registry: dict[str, ResolvedType] = {}
    result: list[dict] = []

    for node in _walk(tree.root_node):
        if node.type != "struct_item":
            continue
        name_node = node.child_by_field_name("name") or _child(node, "type_identifier")
        if name_node is None:
            continue
        name = _text(name_node)
        fields = _extract_fields(node, registry)
        if not fields:
            continue

        layout = compute_layout(fields, X86_64)
        registry[name] = ResolvedType(layout["total_size"], layout["alignment"])
        result.append({"name": name, "fields": fields, "line": node.start_point[0] + 1})

    return result


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(parse_structs_rust(sys.stdin.read()), indent=2))
