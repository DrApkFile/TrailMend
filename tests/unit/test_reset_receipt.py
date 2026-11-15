import json
from pathlib import Path

import pytest

from trailmend.core.receipts import RESET_KIND, make_reset_receipt, reset_to_json
from trailmend.loop.journal import Journal

RESTORED = {"quarantines_cleared": 17, "shortcuts_cleared": 3, "pool_edges_withheld": 128, "rounds_discarded": 4}


def test_a_reset_is_a_receipt_with_a_digest_over_what_it_restored() -> None:
    receipt = make_reset_receipt("live", 4, 912, RESTORED)
    assert receipt.kind == RESET_KIND
    assert receipt.receipt_id.startswith("rcpt-")
    assert len(receipt.digest) == 64
    assert receipt.restored == RESTORED


def test_the_same_reset_digests_the_same_and_a_different_one_does_not() -> None:
    first = make_reset_receipt("live", 4, 912, RESTORED)
    again = make_reset_receipt("live", 4, 912, dict(RESTORED))
    other = make_reset_receipt("live", 4, 912, RESTORED | {"quarantines_cleared": 18})
    assert first.digest == again.digest
    assert first.digest != other.digest


def test_a_reset_receipt_is_refused_before_it_is_written_if_its_place_makes_no_sense() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        make_reset_receipt("live", -1, 0, RESTORED)


def test_a_reset_lands_in_the_same_receipt_stream_as_every_other_change(tmp_path: Path) -> None:
    journal = Journal.for_run("live", tmp_path)
    receipt = make_reset_receipt("live", 2, 7, RESTORED)
    journal.append_reset(receipt)

    lines = journal.lines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["kind"] == RESET_KIND
    assert row["receipt_id"] == receipt.receipt_id
    assert row["restored"]["quarantines_cleared"] == 17
    assert "before" not in row
    assert json.loads(reset_to_json(receipt)) == row
