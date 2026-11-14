import pytest

from trailmend.graph.queries import quarantine_type, require_label, require_searchable, weighted_paths_from
from trailmend.graph.values import DecodeError, PathValue, decode_cell

REAL_RELATIONSHIPS: list[object] = [
    {"id": None, "edge_type": "R", "src": 10, "dst": 11, "properties": {"cost": {"Float": 1.4}}}
]
REAL_PATH_CELL: dict[str, object] = {
    "type": "path",
    "value": {
        "nodes": [
            {"id": 10, "labels": ["N"], "properties": {}},
            {"id": 11, "labels": ["N"], "properties": {}},
        ],
        "relationships": [{"id": None, "edge_type": "R", "src": 10, "dst": 11, "properties": {"cost": {"Float": 1.4}}}],
    },
}


def test_decodes_a_path_cell_captured_from_hydradb() -> None:
    path = decode_cell(REAL_PATH_CELL)
    assert isinstance(path, PathValue)
    assert path.node_ids == (10, 11)
    assert path.rels[0].props["cost"] == 1.4


def test_a_cell_without_a_value_key_is_null_not_an_error() -> None:
    assert decode_cell({"type": "float"}) is None


def test_integral_float_cells_stay_floats() -> None:
    assert decode_cell({"type": "float", "value": 2}) == 2.0
    assert isinstance(decode_cell({"type": "float", "value": 2}), float)


def test_rejects_a_boolean_where_a_vertex_id_is_expected() -> None:
    with pytest.raises(DecodeError):
        decode_cell({"type": "vertex_id", "value": True})


def test_rejects_unknown_cell_types_instead_of_guessing() -> None:
    with pytest.raises(DecodeError):
        decode_cell({"type": "mystery", "value": 1})


def test_rejects_a_path_whose_node_and_edge_counts_disagree() -> None:
    broken: dict[str, object] = {"type": "path", "value": {"nodes": [{"id": 1}], "relationships": REAL_RELATIONSHIPS}}
    with pytest.raises(DecodeError):
        decode_cell(broken)


def test_quarantined_types_can_never_be_searched() -> None:
    with pytest.raises(ValueError, match="never be searched"):
        weighted_paths_from(["OWNED_BY", quarantine_type("OWNED_BY")], 3, 10)
    with pytest.raises(ValueError, match="never be searched"):
        require_searchable("Q_OWNED_BY")


@pytest.mark.parametrize("bad", ["owned_by", "OWNED-BY", "X) DETACH DELETE (n", ""])
def test_rejects_identifiers_that_could_inject_cypher(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid relationship type"):
        require_searchable(bad)
    with pytest.raises(ValueError, match="invalid node label"):
        require_label(bad)
