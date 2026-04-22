from pathlib import Path

import pytest

from purser.beads import BeadsClient, BeadsError


class StubBeadsClient(BeadsClient):
    def __init__(self, responses):
        super().__init__(Path("."))
        self.responses = list(responses)

    def _run(self, *args: str, check: bool = True):
        del args, check
        return self.responses.pop(0)


def test_show_accepts_nested_issue_shape() -> None:
    client = StubBeadsClient([{"output": [{"issue": {"id": "bd-1", "title": "One", "status": "open"}}]}])

    bead = client.show("bd-1")

    assert bead.id == "bd-1"
    assert bead.title == "One"
    assert bead.normalized_status == "open"


def test_create_accepts_nested_items_shape() -> None:
    client = StubBeadsClient([{"data": {"items": [{"id": "bd-2", "title": "Two", "status": "in-review"}]}}])

    bead = client.create("Two")

    assert bead.id == "bd-2"
    assert bead.normalized_status == "in_review"


def test_show_raises_on_unparseable_output() -> None:
    client = StubBeadsClient(["not json"])

    with pytest.raises(BeadsError):
        client.show("bd-404")
