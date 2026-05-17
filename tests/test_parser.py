from pathlib import Path

from parser_c import parse_structs
from parser_rust import parse_structs_rust


FIXTURES = Path(__file__).parent / "fixtures"


def test_c_struct_with_three_fields_parses_names():
    source = (FIXTURES / "sample_c.h").read_text(encoding="utf-8")
    structs = parse_structs(source, "c")
    by_name = {struct["name"]: struct for struct in structs}
    assert "FourByteFields" in by_name
    assert [field["name"] for field in by_name["FourByteFields"]["fields"]] == ["a", "b", "c"]


def test_typedef_struct_detected():
    source = (FIXTURES / "sample_c.h").read_text(encoding="utf-8")
    structs = parse_structs(source, "c")
    assert any(struct["name"] == "AliasStruct" for struct in structs)


def test_rust_struct_parses_field_names_and_types():
    source = (FIXTURES / "sample_rust.rs").read_text(encoding="utf-8")
    structs = parse_structs_rust(source)
    by_name = {struct["name"]: struct for struct in structs}
    assert "RustMixed" in by_name
    assert [(field["name"], field["raw_type"]) for field in by_name["RustMixed"]["fields"]] == [
        ("tag", "u8"),
        ("value", "f64"),
        ("state", "u8"),
    ]


def test_rust_common_primitives_include_char_and_128_bit_integers():
    structs = parse_structs_rust("struct Wide { marker: char, value: u128, signed: i128 }")
    wide = structs[0]
    fields = {field["name"]: field for field in wide["fields"]}
    assert fields["marker"]["size"] == 4
    assert fields["marker"]["alignment"] == 4
    assert fields["value"]["size"] == 16
    assert fields["signed"]["size"] == 16
