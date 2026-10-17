"""Three-way merge of editable project fields. Pure functions, no I/O, no state.

Inputs are plain dicts shaped like `models.Editable` dumped to JSON:
    {"name", "sector", "country", "stage", "key_dates": [{"label", "date"}]}

    base   what the person loaded when they opened the form
    mine   what the form holds now
    theirs what the upstream holds right now (may include other people's saves, or the nightly job's)

Per field:
    mine == base                -> the person did not touch it: take theirs
    theirs == base              -> only the person changed it: take mine
    mine == theirs              -> both made the same change: take it (this is what makes a retry safe)
    otherwise                   -> conflict; the merged value keeps theirs until the person decides

What "the same field" means:
    name, sector, country, stage  each is one field.
    key_dates                     each ENTRY is one field, identified by its label. Two people editing different
                                  milestones never conflict. Changing a date, removing an entry and adding an
                                  entry are all changes to that label's field. Renaming a label is a removal of
                                  the old label plus an addition of the new one, so a concurrent edit of the
                                  old label's date conflicts with it, which is the safe reading.
    Fallback: entries have no ids, so if any side holds duplicate labels we cannot tell the entries apart.
    Then the whole key_dates list becomes ONE field (coarse, but never wrong).
"""

from dataclasses import dataclass
from typing import Any

SCALAR_FIELDS = ("name", "sector", "country", "stage")


@dataclass(frozen=True)
class Conflict:
    key: str  # "name" | "key_dates:<label>" | "key_dates"
    kind: str  # "scalar" | "key_date" | "key_dates_list"
    field: str
    label: str | None
    base: Any
    theirs: Any
    mine: Any


@dataclass
class MergeResult:
    merged: dict
    conflicts: list[Conflict]
    incoming: list[str]  # keys where another writer's change was kept


def has_duplicate_labels(key_dates: list[dict]) -> bool:
    labels = [d["label"] for d in key_dates]
    return len(set(labels)) != len(labels)


def _decide(base: Any, mine: Any, theirs: Any) -> str:
    if mine == base:
        return "theirs"
    if theirs == base or mine == theirs:
        return "mine"
    return "conflict"


def merge(base: dict, mine: dict, theirs: dict) -> MergeResult:
    merged: dict = {}
    conflicts: list[Conflict] = []
    incoming: list[str] = []

    for name in SCALAR_FIELDS:
        b, m, t = base[name], mine[name], theirs[name]
        decision = _decide(b, m, t)
        if decision == "mine":
            merged[name] = m
            continue
        merged[name] = t
        if decision == "conflict":
            conflicts.append(Conflict(name, "scalar", name, None, b, t, m))
        elif t != b:
            incoming.append(name)

    merged["key_dates"] = _merge_key_dates(base["key_dates"], mine["key_dates"], theirs["key_dates"], conflicts, incoming)
    return MergeResult(merged=merged, conflicts=conflicts, incoming=incoming)


def _canonical(key_dates: list[dict]) -> list[tuple[str, str]]:
    return sorted((d["label"], d["date"]) for d in key_dates)


def _merge_key_dates(base: list[dict], mine: list[dict], theirs: list[dict], conflicts: list[Conflict], incoming: list[str]) -> list[dict]:
    if any(has_duplicate_labels(side) for side in (base, mine, theirs)):
        decision = _decide(_canonical(base), _canonical(mine), _canonical(theirs))
        if decision == "mine":
            return [dict(d) for d in mine]
        if decision == "conflict":
            conflicts.append(Conflict("key_dates", "key_dates_list", "key_dates", None, base, theirs, mine))
        elif _canonical(theirs) != _canonical(base):
            incoming.append("key_dates")
        return [dict(d) for d in theirs]

    base_map = {d["label"]: d["date"] for d in base}
    mine_map = {d["label"]: d["date"] for d in mine}
    theirs_map = {d["label"]: d["date"] for d in theirs}

    # Stored order is kept; additions go at the end; labels only the base knew about cannot produce output.
    order = list(theirs_map)
    order += [label for label in mine_map if label not in theirs_map]
    order += [label for label in base_map if label not in theirs_map and label not in mine_map]

    result: list[dict] = []
    for label in order:
        b, m, t = base_map.get(label), mine_map.get(label), theirs_map.get(label)
        decision = _decide(b, m, t)
        if decision == "mine":
            value = m
        else:
            value = t
            key = f"key_dates:{label}"
            if decision == "conflict":
                conflicts.append(Conflict(key, "key_date", "key_dates", label, b, t, m))
            elif t != b:
                incoming.append(key)
        if value is not None:
            result.append({"label": label, "date": value})
    return result
