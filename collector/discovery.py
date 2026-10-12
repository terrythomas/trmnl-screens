"""Finds every screen under screens/ that has a collector package."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

Collect = Callable[[], dict[str, Any]]

SCREENS_DIR = Path(__file__).resolve().parent.parent / "screens"


def discover_screens(screens_dir: Path = SCREENS_DIR) -> dict[str, Collect]:
    """Map each screen name to its collector's collect() function."""
    screens = {}
    for init in sorted(screens_dir.glob("*/collector/__init__.py")):
        name = init.parent.parent.name
        screens[name] = _load(name, init).collect
    return screens


def _load(name: str, init: Path):
    # Every screen's package is called "collector", so give each a unique module name.
    module_name = f"trmnl_screens.{name}.collector"
    spec = importlib.util.spec_from_file_location(
        module_name, init, submodule_search_locations=[str(init.parent)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
