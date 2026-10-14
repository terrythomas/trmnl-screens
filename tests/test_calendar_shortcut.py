import importlib.util
import plistlib
from pathlib import Path

SHORTCUT_DIR = Path(__file__).resolve().parent.parent / "screens" / "calendar" / "shortcut"


def load_build():
    spec = importlib.util.spec_from_file_location("calendar_shortcut_build", SHORTCUT_DIR / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_shortcut_matches_build_py():
    build = load_build()
    committed = plistlib.loads((SHORTCUT_DIR / "Calendar Sync.shortcut").read_bytes())
    assert committed == plistlib.loads(plistlib.dumps(build.workflow)), "run screens/calendar/shortcut/build.py"


def test_every_variable_sits_on_a_placeholder():
    # A range that misses its placeholder can crash Shortcuts on import.
    def walk(node):
        if isinstance(node, dict):
            if "attachmentsByRange" in node:
                s = node["string"]
                for key in node["attachmentsByRange"]:
                    pos = int(key.strip("{}").split(",")[0])
                    assert s[pos] == "￼", (s, key)
                assert s.count("￼") == len(node["attachmentsByRange"]), s
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(load_build().workflow)
