import sys
from pathlib import Path

from file_sorter.rules import category_for, default_rules_path, load_rules


def test_known_extension_and_fallback() -> None:
    rules = load_rules()

    assert category_for(rules, "photo.png") == "Images"
    assert category_for(rules, "PHOTO.PNG") == "Images"
    assert category_for(rules, "notes.txt") == "Others"
    assert category_for(rules, "archive.tar.gz") == "Others"
    assert category_for(rules, "README") == "Others"


def test_frozen_bundle_reads_the_extracted_rules(
    tmp_path: Path, monkeypatch
) -> None:
    bundled = tmp_path / "file_sorter" / "data"
    bundled.mkdir(parents=True)
    payload = bundled / "default_rules.json"
    payload.write_text('{"categories": [], "fallback": "Kept"}', encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    rules = load_rules()

    assert default_rules_path() == payload
    assert rules.fallback == "Kept"
