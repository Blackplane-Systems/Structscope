import pytest

from server import analyse_source


def test_unresolved_c_type_fails_fast_by_default():
    source = "struct Bad { MissingType value; int count; };"
    with pytest.raises(ValueError, match="Exact layout unavailable"):
        analyse_source(source, "c", "x86_64", 64)


def test_unresolved_c_type_can_be_marked_incomplete_when_allowed():
    source = "struct Bad { MissingType value; int count; };"
    result = analyse_source(source, "c", "x86_64", 64, allow_incomplete=True)
    bad = result["structs"][0]
    assert result["layout_complete"] is False
    assert bad["layout"]["complete"] is False
    assert bad["analysis"]["layout_complete"] is False
    assert any(rule["id"] == "analysis.unresolved_type" for rule in bad["analysis"]["rules"])


def test_bitfield_layout_fails_fast_by_default():
    source = "struct Flags { unsigned int a:1; unsigned int b:3; int tail; };"
    with pytest.raises(ValueError, match="bit-field"):
        analyse_source(source, "c", "x86_64", 64)


def test_bitfield_partial_analysis_is_penalized_when_allowed():
    source = "struct Flags { unsigned int a:1; unsigned int b:3; int tail; };"
    result = analyse_source(source, "c", "x86_64", 64, allow_incomplete=True)
    analysis = result["structs"][0]["analysis"]
    assert analysis["layout_score"] < 100
    assert any(rule["id"] == "portability.bitfield_layout" for rule in analysis["rules"])


def test_source_model_reports_single_text_no_preprocessor():
    source = '#include "types.h"\nstruct Foo { int a; };'
    result = analyse_source(source, "c", "x86_64", 64)
    assert result["source_model"]["preprocessor"] is False
    assert result["source_model"]["include_count"] == 1
