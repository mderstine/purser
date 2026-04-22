from pathlib import Path

from purser.validation import ValidationRecord, append_validation_log


def test_append_validation_log(tmp_path: Path) -> None:
    path = tmp_path / "VALIDATION.md"
    append_validation_log(
        path,
        ValidationRecord(
            bead_id="bd-1",
            title="Test bead",
            spec_reference="specs/demo.md §1",
            summary="Implemented the thing.",
            verification_items=["lint: clean", "tests: clean"],
            notes=["note one"],
        ),
    )
    text = path.read_text(encoding="utf-8")
    assert "## bd-1 — Test bead" in text
    assert "### Verification" in text
    assert "- lint: clean" in text
