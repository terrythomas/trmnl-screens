import importlib.util
import json
from datetime import datetime
from pathlib import Path

SCREEN = Path(__file__).resolve().parent.parent


def load_collector():
    spec = importlib.util.spec_from_file_location("media_collector", SCREEN / "collector" / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_updated_at_is_local_time_with_offset():
    updated_at = datetime.fromisoformat(load_collector().collect()["updated_at"])
    assert updated_at.utcoffset() is not None


def test_sample_fixture_covers_every_payload_key():
    sample = json.loads((SCREEN / "fixtures" / "sample.json").read_text())
    assert set(sample) == {"updated_at", "errors", "continue_watching", "airing", "releasing_today"}
    for section in ("continue_watching", "airing", "releasing_today"):
        assert {"stale", "items"} <= set(sample[section])
