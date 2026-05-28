"""Load config.yaml into a typed dataclass tree."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass(frozen=True)
class DatasetCfg:
    name: Optional[str]
    split: str
    config: Optional[str]
    revision: Optional[str]


@dataclass(frozen=True)
class FieldsCfg:
    id: str
    title: str
    text: str
    url: str
    date: str
    source: Optional[str]
    score: Optional[str]


@dataclass(frozen=True)
class FilterCfg:
    days_back: int
    max_items: int
    rank_by_score: bool


@dataclass(frozen=True)
class LLMCfg:
    model: str
    max_tokens: int


@dataclass(frozen=True)
class NewsletterCfg:
    title: str
    sections: list[str]


@dataclass(frozen=True)
class PathsCfg:
    state: Path
    output_dir: Path
    latest: Path
    eval_dir: Path


@dataclass(frozen=True)
class PersonalizationCfg:
    default_profile: str


@dataclass(frozen=True)
class EvaluationCfg:
    enabled: bool


@dataclass(frozen=True)
class Config:
    dataset: DatasetCfg
    fields: FieldsCfg
    filter: FilterCfg
    llm: LLMCfg
    newsletter: NewsletterCfg
    paths: PathsCfg
    personalization: PersonalizationCfg
    evaluation: EvaluationCfg


def load(path: str | Path = "config.yaml") -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    return Config(
        dataset=DatasetCfg(**raw["dataset"]),
        fields=FieldsCfg(**raw["fields"]),
        filter=FilterCfg(**raw["filter"]),
        llm=LLMCfg(**raw["llm"]),
        newsletter=NewsletterCfg(**raw["newsletter"]),
        paths=PathsCfg(
            state=Path(raw["paths"]["state"]),
            output_dir=Path(raw["paths"]["output_dir"]),
            latest=Path(raw["paths"]["latest"]),
            eval_dir=Path(raw["paths"]["eval_dir"]),
        ),
        personalization=PersonalizationCfg(**raw["personalization"]),
        evaluation=EvaluationCfg(**raw["evaluation"]),
    )
