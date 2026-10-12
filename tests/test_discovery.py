from collector.discovery import discover_screens


def test_discovers_every_screen_with_a_collector(tmp_path):
    for name, value in [("alpha", 1), ("beta", 2)]:
        pkg = tmp_path / name / "collector"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(f"def collect():\n    return {{'value': {value}}}\n")
    (tmp_path / "no_collector" / "src").mkdir(parents=True)

    screens = discover_screens(tmp_path)

    assert sorted(screens) == ["alpha", "beta"]
    assert screens["beta"]() == {"value": 2}


def test_discovers_the_media_screen():
    assert "media" in discover_screens()
