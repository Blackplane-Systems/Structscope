"""Rule-based, local-only layout improvement guidance."""

from __future__ import annotations


Severity = str


def evaluate_rules(layout_result: dict, analysis_result: dict, platform_name: str, cache_line_size: int = 64) -> dict:
    fields = list(layout_result.get("fields") or [])
    total_size = int(layout_result.get("total_size") or 0)
    waste_bytes = int(analysis_result.get("waste_bytes") or 0)
    waste_ratio = float(analysis_result.get("waste_ratio") or 0.0)
    savings = int(analysis_result.get("savings") or 0)
    splits = list(analysis_result.get("cache_line_splits") or [])
    rules: list[dict] = []

    if waste_ratio >= 0.30:
        rules.append(
            _rule(
                "padding.high_waste",
                "critical" if waste_ratio >= 0.45 else "warning",
                "padding",
                "High padding waste",
                f"{waste_bytes} of {total_size} bytes are padding ({waste_ratio * 100:.1f}%).",
                "Reorder fields by alignment or group small fields together to reduce internal padding.",
                savings_bytes=savings,
            )
        )
    elif waste_ratio >= 0.10:
        rules.append(
            _rule(
                "padding.moderate_waste",
                "info",
                "padding",
                "Moderate padding waste",
                f"{waste_bytes} of {total_size} bytes are padding ({waste_ratio * 100:.1f}%).",
                "Check whether the current order is required for ABI compatibility before changing it.",
                savings_bytes=savings,
            )
        )

    if savings > 0:
        ordered_names = [str(field.get("name", "")) for field in analysis_result.get("optimal_order", [])]
        rules.append(
            _rule(
                "layout.reorder_fields",
                "suggestion",
                "layout",
                "Field reorder can reduce size",
                f"The greedy alignment order saves {savings} bytes on {platform_name}.",
                "Use the suggested order only when binary compatibility and serialization layout are not externally fixed.",
                fields=ordered_names,
                savings_bytes=savings,
            )
        )

    if splits:
        for split in splits:
            rules.append(
                _rule(
                    "cache.field_split",
                    "warning",
                    "cache",
                    "Field crosses a cache-line boundary",
                    f"Field {split['field_name']} spans byte {split['offset']} across a {split['line_size']} byte cache line.",
                    "Consider moving the field earlier, adding explicit alignment, or separating hot fields from cold payload data.",
                    fields=[split["field_name"]],
                )
            )

    if total_size > int(cache_line_size or 64):
        rules.append(
            _rule(
                "cache.large_struct",
                "info",
                "cache",
                "Struct is larger than one cache line",
                f"Total size is {total_size} bytes with a {cache_line_size} byte cache line.",
                "For hot paths, consider splitting frequently accessed fields from rarely used payload fields.",
            )
        )

    pointer_fields = [field for field in fields if _is_pointer_like(field)]
    if pointer_fields:
        rules.append(
            _rule(
                "portability.pointer_width",
                "info",
                "portability",
                "Layout depends on pointer width",
                f"{len(pointer_fields)} field(s) use pointer-sized storage.",
                "Compare target platforms before assuming offsets are stable across 32-bit and 64-bit builds.",
                fields=[str(field.get("name", "")) for field in pointer_fields],
            )
        )

    unresolved_fields = [field for field in fields if field.get("unresolved") or int(field.get("size") or 0) == 0]
    if unresolved_fields:
        rules.append(
            _rule(
                "analysis.unresolved_type",
                "critical",
                "analysis",
                "One or more field types could not be resolved",
                "The layout is incomplete because at least one field type is unresolved.",
                "Add the dependent type definition to the analyzed source, use a supported primitive/platform type, or rerun with allow_incomplete only for non-authoritative inspection.",
                fields=[str(field.get("name", "")) for field in unresolved_fields],
                confidence="high",
            )
        )

    bit_fields = [field for field in fields if "bit_width" in field]
    if bit_fields:
        rules.append(
            _rule(
                "portability.bitfield_layout",
                "warning",
                "portability",
                "Bit-field layout requires compiler-specific packing rules",
                f"{len(bit_fields)} bit-field member(s) were detected.",
                "StructScope refuses exact bit-field layouts by default; use allow_incomplete only for a partial view and verify with the target compiler.",
                fields=[str(field.get("name", "")) for field in bit_fields],
                confidence="high",
            )
        )

    one_byte_fields = [field for field in fields if int(field.get("size") or 0) == 1]
    if len(one_byte_fields) >= 2 and waste_bytes > 0:
        rules.append(
            _rule(
                "layout.group_small_fields",
                "suggestion",
                "layout",
                "Small fields are separated by padding",
                f"{len(one_byte_fields)} one-byte field(s) exist in a padded layout.",
                "Group small scalar fields together when source compatibility allows it.",
                fields=[str(field.get("name", "")) for field in one_byte_fields],
                savings_bytes=savings,
            )
        )

    score = _score(total_size, waste_ratio, savings, splits, unresolved_fields, bit_fields)
    return {
        "score": score,
        "grade": _grade(score),
        "rules": rules,
        "rule_count": len(rules),
    }


def _rule(
    rule_id: str,
    severity: Severity,
    category: str,
    title: str,
    message: str,
    recommendation: str,
    *,
    fields: list[str] | None = None,
    savings_bytes: int = 0,
    confidence: str = "high",
) -> dict:
    return {
        "id": rule_id,
        "severity": severity,
        "category": category,
        "title": title,
        "message": message,
        "recommendation": recommendation,
        "fields": fields or [],
        "savings_bytes": savings_bytes,
        "confidence": confidence,
        "safe": True,
        "auto_apply": False,
    }


def _is_pointer_like(field: dict) -> bool:
    raw_type = str(field.get("raw_type") or field.get("type") or "").strip()
    return "*" in raw_type or raw_type in {"pointer", "usize", "isize", "&"}


def _score(total_size: int, waste_ratio: float, savings: int, splits: list, unresolved_fields: list, bit_fields: list) -> int:
    score = 100
    score -= min(45, round(waste_ratio * 100))
    if savings > 0:
        score -= min(20, max(4, savings // 2))
    score -= min(20, len(splits) * 8)
    score -= min(20, len(unresolved_fields) * 10)
    score -= min(25, len(bit_fields) * 12)
    if total_size >= 256:
        score -= 8
    elif total_size >= 128:
        score -= 4
    return max(0, min(100, score))


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"
