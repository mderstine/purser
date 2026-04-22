from purser.beads import _items_from_json, normalize_status


def test_normalize_status() -> None:
    assert normalize_status("in-review") == "in_review"
    assert normalize_status("in_progress") == "in_progress"
    assert normalize_status("OPEN") == "open"


def test_items_from_json_shapes() -> None:
    assert _items_from_json([{"id": "bd-1"}]) == [{"id": "bd-1"}]
    assert _items_from_json({"issues": [{"id": "bd-2"}]}) == [{"id": "bd-2"}]
    assert _items_from_json({"issue": {"id": "bd-3"}}) == [{"id": "bd-3"}]
    assert _items_from_json({"id": "bd-4", "title": "x"}) == [{"id": "bd-4", "title": "x"}]
