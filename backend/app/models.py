"""API shapes the browser sees. Deliberately much narrower than the upstream records."""

from datetime import date as Date
from typing import Any, Literal

from pydantic import BaseModel, Field

SECTORS = ("energy", "mining", "water", "transport", "oil_and_gas", "ict")
STAGES = ("idea", "feasibility", "tender", "financing", "construction", "operation", "cancelled")

Sector = Literal["energy", "mining", "water", "transport", "oil_and_gas", "ict"]
Stage = Literal["idea", "feasibility", "tender", "financing", "construction", "operation", "cancelled"]


class KeyDate(BaseModel):
    label: str = Field(min_length=1)
    date: Date


class Editable(BaseModel):
    """The fields this tool edits. linked_companies is not here on purpose: see DECISIONS.md."""

    name: str = Field(min_length=1)
    sector: Sector
    country: str = Field(min_length=1)
    stage: Stage
    key_dates: list[KeyDate]


class Project(Editable):
    id: str


class ProjectSummary(BaseModel):
    id: str
    name: str
    sector: str
    country: str
    stage: str
    key_dates_count: int


class SaveRequest(BaseModel):
    """`base` is the snapshot the person loaded; `edited` is what the form holds now."""

    base: Editable
    edited: Editable


class SaveResponse(BaseModel):
    project: Project
    # Keys of fields other people changed since `base`, which are now part of `project`.
    also_changed_by_others: list[str]


class ConflictOut(BaseModel):
    key: str  # "name" | "key_dates:<label>" | "key_dates"
    kind: Literal["scalar", "key_date", "key_dates_list"]
    field: str
    label: str | None
    base: Any
    theirs: Any
    mine: Any


class ConflictResponse(BaseModel):
    code: Literal["conflict"] = "conflict"
    current: Project  # what is stored now: the new base for a retry
    conflicts: list[ConflictOut]
    # `current` plus this person's non-conflicting edits; conflicting fields still hold `theirs`.
    proposed: Editable


class Options(BaseModel):
    sectors: list[str]
    stages: list[str]
