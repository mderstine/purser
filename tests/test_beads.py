from purser.beads import _items_from_json, normalize_status, parse_bd_json_output


def test_normalize_status() -> None:
    assert normalize_status("in-review") == "in_review"
    assert normalize_status("in_progress") == "in_progress"
    assert normalize_status("OPEN") == "open"


def test_items_from_json_shapes() -> None:
    assert _items_from_json([{"id": "bd-1"}]) == [{"id": "bd-1"}]
    assert _items_from_json({"issues": [{"id": "bd-2"}]}) == [{"id": "bd-2"}]
    assert _items_from_json({"issue": {"id": "bd-3"}}) == [{"id": "bd-3"}]
    assert _items_from_json({"id": "bd-4", "title": "x"}) == [{"id": "bd-4", "title": "x"}]
    assert _items_from_json({"data": {"items": [{"id": "bd-5"}]}}) == [{"id": "bd-5"}]
    assert _items_from_json({"output": [{"issue": {"id": "bd-6"}}]}) == [{"id": "bd-6"}]


def test_parse_bd_json_output_supports_jsonl() -> None:
    parsed = parse_bd_json_output('{"id": "bd-1"}\n{"id": "bd-2"}\n')
    assert parsed == [{"id": "bd-1"}, {"id": "bd-2"}]


def test_parse_bd_json_output_returns_raw_text_when_unparseable() -> None:
    parsed = parse_bd_json_output('Error: no beads database found')
    assert parsed == 'Error: no beads database found'
