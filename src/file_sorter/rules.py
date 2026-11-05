from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Category:
    folder: str
    extensions: frozenset[str]


@dataclass(frozen=True)
class Rules:
    categories: tuple[Category, ...]
    fallback: str


def default_rules_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "default_rules.json"


def load_rules(path: Path | None = None) -> Rules:
    rules_path = path or default_rules_path()
    try:
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        categories = tuple(
            Category(
                folder=str(item["folder"]),
                extensions=frozenset(
                    str(extension).lower().lstrip(".") for extension in item["extensions"]
                ),
            )
            for item in payload["categories"]
        )
        fallback = str(payload.get("fallback") or "Others")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"Cannot read rules: {exc}") from exc
    return Rules(categories=categories, fallback=fallback)


def category_for(rules: Rules, filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if not suffix:
        return rules.fallback
    for category in rules.categories:
        if suffix in category.extensions:
            return category.folder
    return rules.fallback


def category_dir(root: Path, folder_name: str) -> Path:
    if not folder_name.strip():
        raise ValueError("A category folder is required.")
    root_resolved = root.resolve()
    destination = (root_resolved / folder_name).resolve()
    if destination == root_resolved or root_resolved not in destination.parents:
        raise ValueError(f"Category escapes the chosen folder: {folder_name}")
    return destination
