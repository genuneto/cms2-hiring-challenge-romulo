"""The merge rules, with no I/O. These are the definition of "same field"."""

import copy

from app.merge import merge

BASE = {
    "name": "Alpha Solar Park",
    "sector": "energy",
    "country": "Chile",
    "stage": "tender",
    "key_dates": [
        {"label": "Tender launch", "date": "2026-12-16"},
        {"label": "Financial close", "date": "2027-07-04"},
    ],
}


def variant(**changes):
    out = copy.deepcopy(BASE)
    out.update(changes)
    return out


def dates(**by_label):
    return [{"label": k.replace("_", " "), "date": v} for k, v in by_label.items()]


def test_different_scalar_fields_both_survive():
    result = merge(BASE, variant(name="Mine"), variant(country="Peru"))
    assert not result.conflicts
    assert (result.merged["name"], result.merged["country"]) == ("Mine", "Peru")
    assert result.incoming == ["country"]


def test_same_scalar_field_different_values_conflicts_and_keeps_theirs_meanwhile():
    result = merge(BASE, variant(stage="financing"), variant(stage="construction"))
    assert [(c.key, c.base, c.theirs, c.mine) for c in result.conflicts] == [("stage", "tender", "construction", "financing")]
    assert result.merged["stage"] == "construction"


def test_same_scalar_field_same_value_is_not_a_conflict():
    result = merge(BASE, variant(stage="financing"), variant(stage="financing"))
    assert not result.conflicts and result.merged["stage"] == "financing"


def test_untouched_form_takes_everything_from_theirs():
    result = merge(BASE, BASE, variant(name="Theirs", stage="operation"))
    assert not result.conflicts and result.merged["name"] == "Theirs" and result.merged["stage"] == "operation"
    assert set(result.incoming) == {"name", "stage"}


def test_key_dates_different_labels_both_survive():
    mine = variant(key_dates=dates(Tender_launch="2026-12-30", Financial_close="2027-07-04"))
    theirs = variant(key_dates=dates(Tender_launch="2026-12-16", Financial_close="2027-08-01"))
    result = merge(BASE, mine, theirs)
    assert not result.conflicts
    assert result.merged["key_dates"] == dates(Tender_launch="2026-12-30", Financial_close="2027-08-01")


def test_key_date_same_label_different_dates_conflicts():
    mine = variant(key_dates=dates(Tender_launch="2026-12-30", Financial_close="2027-07-04"))
    theirs = variant(key_dates=dates(Tender_launch="2027-01-10", Financial_close="2027-07-04"))
    result = merge(BASE, mine, theirs)
    assert [(c.key, c.kind, c.label, c.theirs, c.mine) for c in result.conflicts] == [
        ("key_dates:Tender launch", "key_date", "Tender launch", "2027-01-10", "2026-12-30")
    ]
    assert {"label": "Tender launch", "date": "2027-01-10"} in result.merged["key_dates"]


def test_key_date_removed_by_one_and_untouched_by_other_is_removed():
    mine = variant(key_dates=dates(Tender_launch="2026-12-16"))
    result = merge(BASE, mine, BASE)
    assert not result.conflicts and result.merged["key_dates"] == dates(Tender_launch="2026-12-16")


def test_key_date_removed_by_one_edited_by_other_conflicts():
    mine = variant(key_dates=dates(Tender_launch="2026-12-16"))  # I removed Financial close
    theirs = variant(key_dates=dates(Tender_launch="2026-12-16", Financial_close="2027-09-09"))  # they moved it
    result = merge(BASE, mine, theirs)
    assert [(c.key, c.theirs, c.mine) for c in result.conflicts] == [("key_dates:Financial close", "2027-09-09", None)]
    assert {"label": "Financial close", "date": "2027-09-09"} in result.merged["key_dates"]


def test_key_date_removed_by_both_is_fine():
    only_tender = variant(key_dates=dates(Tender_launch="2026-12-16"))
    result = merge(BASE, only_tender, only_tender)
    assert not result.conflicts and result.merged["key_dates"] == dates(Tender_launch="2026-12-16")


def test_added_key_dates_with_different_labels_both_survive():
    mine = variant(key_dates=BASE["key_dates"] + dates(Construction_start="2028-01-01"))
    theirs = variant(key_dates=BASE["key_dates"] + dates(Commercial_operation="2029-01-01"))
    result = merge(BASE, mine, theirs)
    assert not result.conflicts
    assert [d["label"] for d in result.merged["key_dates"]] == ["Tender launch", "Financial close", "Commercial operation", "Construction start"]


def test_added_key_date_same_label_different_dates_conflicts_same_date_does_not():
    mine = variant(key_dates=BASE["key_dates"] + dates(Construction_start="2028-01-01"))
    theirs_other = variant(key_dates=BASE["key_dates"] + dates(Construction_start="2028-02-02"))
    theirs_same = variant(key_dates=BASE["key_dates"] + dates(Construction_start="2028-01-01"))
    assert [c.key for c in merge(BASE, mine, theirs_other).conflicts] == ["key_dates:Construction start"]
    assert not merge(BASE, mine, theirs_same).conflicts


def test_duplicate_labels_fall_back_to_the_whole_list_as_one_field():
    dup_base = variant(key_dates=dates(Tender_launch="2026-12-16") + dates(Tender_launch="2027-01-01"))
    mine = copy.deepcopy(dup_base)
    mine["key_dates"][0]["date"] = "2026-12-20"
    theirs = copy.deepcopy(dup_base)
    theirs["key_dates"][1]["date"] = "2027-02-02"
    result = merge(dup_base, mine, theirs)
    assert [(c.key, c.kind) for c in result.conflicts] == [("key_dates", "key_dates_list")]
    # and an untouched list simply follows theirs
    assert merge(dup_base, dup_base, theirs).merged["key_dates"] == theirs["key_dates"]


def test_merging_the_result_again_changes_nothing():
    """The property that makes retries after a 504 safe."""
    mine = variant(name="Mine", key_dates=dates(Tender_launch="2026-12-30", Financial_close="2027-07-04"))
    theirs = variant(country="Peru")
    first = merge(BASE, mine, theirs)
    again = merge(BASE, mine, first.merged)
    assert not again.conflicts and again.merged == first.merged
