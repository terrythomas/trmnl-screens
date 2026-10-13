from collector.discovery import discover_screens


def test_discovers_every_screen_with_a_collector(tmp_path):
    for name, value in [("alpha", 1), ("beta", 2)]:
        pkg = tmp_path / name / "collector"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(f"def collect():\n    return {{'value': {value}}}\n")
    (tmp_path / "no_collector" / "src").mkdir(parents=True)

    screens = discover_screens(tmp_path)

    assert sorted(screens) == ["alpha", "beta"]
    assert screens["beta"].collect() == {"value": 2}
    assert screens["beta"].interval_minutes is None


def test_discovers_the_media_screen():
    assert "media" in discover_screens()


def test_a_collector_can_split_into_nested_submodules(tmp_path):
    pkg = tmp_path / "gamma" / "collector"
    (pkg / "sources").mkdir(parents=True)
    (pkg / "sources" / "__init__.py").write_text("")
    (pkg / "sources" / "feed.py").write_text("VALUE = 3\n")
    (pkg / "logic.py").write_text("from .sources.feed import VALUE\n")
    (pkg / "__init__.py").write_text("from .logic import VALUE\n\ndef collect():\n    return {'value': VALUE}\n")

    assert discover_screens(tmp_path)["gamma"].collect() == {"value": 3}


def test_a_screen_can_declare_its_default_interval(tmp_path):
    pkg = tmp_path / "slow" / "collector"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("INTERVAL_MINUTES = 60\n\ndef collect():\n    return {}\n")

    assert discover_screens(tmp_path)["slow"].interval_minutes == 60
