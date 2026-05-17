from layout_engine import compute_layout, compute_optimal_order
from platforms import PLATFORMS


def test_zero_padding_same_size_fields():
    fields = [
        {"name": "a", "type": "int", "size": 4, "alignment": 4},
        {"name": "b", "type": "int", "size": 4, "alignment": 4},
        {"name": "c", "type": "float", "size": 4, "alignment": 4},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    assert layout["total_padding"] == 0
    assert layout["total_size"] == 12


def test_mixed_type_offsets_and_padding():
    fields = [
        {"name": "a", "type": "char", "size": 1, "alignment": 1},
        {"name": "b", "type": "int", "size": 4, "alignment": 4},
        {"name": "c", "type": "char", "size": 1, "alignment": 1},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    assert [field["offset"] for field in layout["fields"]] == [0, 4, 8]
    assert layout["fields"][0]["padding_after"] == 3
    assert layout["fields"][1]["padding_after"] == 0
    assert layout["total_padding"] == 6
    assert layout["total_size"] == 12


def test_optimal_reorder_is_smaller_or_equal():
    fields = [
        {"name": "tag", "type": "char", "size": 1, "alignment": 1},
        {"name": "value", "type": "double", "size": 8, "alignment": 8},
        {"name": "state", "type": "char", "size": 1, "alignment": 1},
        {"name": "count", "type": "long long", "size": 8, "alignment": 8},
    ]
    current = compute_layout(fields, PLATFORMS["x86_64"])
    optimal = compute_layout(compute_optimal_order(fields), PLATFORMS["x86_64"])
    assert optimal["total_size"] <= current["total_size"]
    assert optimal["total_size"] == 24


def test_trailing_padding_included_in_total_size():
    fields = [
        {"name": "a", "type": "int", "size": 4, "alignment": 4},
        {"name": "b", "type": "char", "size": 1, "alignment": 1},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    assert layout["total_size"] == 8
    assert layout["total_padding"] == 3
    assert layout["fields"][-1]["padding_after"] == 0


def test_each_platform_computes_a_layout():
    for name, platform in PLATFORMS.items():
        fields = [
            {"name": "a", "type": "char", "size": 1, "alignment": 1},
            {
                "name": "p",
                "type": "pointer",
                "size": platform["type_sizes"]["pointer"],
                "alignment": platform["type_alignments"]["pointer"],
            },
            {"name": "b", "type": "int", "size": platform["type_sizes"]["int"], "alignment": platform["type_alignments"]["int"]},
        ]
        layout = compute_layout(fields, platform)
        assert layout["total_size"] >= sum(field["size"] for field in fields), name
        assert layout["alignment"] <= platform["max_align"], name


def test_pointer_struct_differs_between_x86_64_and_arm32():
    def fields_for(platform):
        return [
            {"name": "tag", "type": "char", "size": 1, "alignment": 1},
            {
                "name": "ptr",
                "type": "pointer",
                "size": platform["type_sizes"]["pointer"],
                "alignment": platform["type_alignments"]["pointer"],
            },
            {"name": "tail", "type": "char", "size": 1, "alignment": 1},
        ]

    x86 = compute_layout(fields_for(PLATFORMS["x86_64"]), PLATFORMS["x86_64"])
    arm32 = compute_layout(fields_for(PLATFORMS["arm32"]), PLATFORMS["arm32"])
    assert x86["total_size"] != arm32["total_size"]
    assert x86["total_size"] == 24
    assert arm32["total_size"] == 12


def test_long_size_differs_between_unix_and_windows_64_bit_abis():
    unix = PLATFORMS["x86_64"]
    windows = PLATFORMS["x86_64_windows"]
    assert unix["type_sizes"]["long"] == 8
    assert windows["type_sizes"]["long"] == 4

    unix_layout = compute_layout(
        [{"name": "value", "type": "long", "size": unix["type_sizes"]["long"], "alignment": unix["type_alignments"]["long"]}],
        unix,
    )
    windows_layout = compute_layout(
        [{"name": "value", "type": "long", "size": windows["type_sizes"]["long"], "alignment": windows["type_alignments"]["long"]}],
        windows,
    )
    assert unix_layout["total_size"] == 8
    assert windows_layout["total_size"] == 4
