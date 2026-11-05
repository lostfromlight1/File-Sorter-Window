from file_sorter.rules import category_for, load_rules


def test_known_extension_and_fallback() -> None:
    rules = load_rules()

    assert category_for(rules, "photo.png") == "Images"
    assert category_for(rules, "PHOTO.PNG") == "Images"
    assert category_for(rules, "notes.txt") == "Others"
    assert category_for(rules, "archive.tar.gz") == "Others"
    assert category_for(rules, "README") == "Others"
