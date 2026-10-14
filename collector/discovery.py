"""Finds the screens under screens/ that have a collector package, and loads them one at a time."""

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

Collect = Callable[[], dict[str, Any]]

SCREENS_DIR = Path(__file__).resolve().parent.parent / "screens"


@dataclass(frozen=True)
class Screen:
    collect: Collect
    # The screen's own default, from INTERVAL_MINUTES in its collector package.
    interval_minutes: int | None = None


def find_screens(screens_dir: Path = SCREENS_DIR) -> dict[str, Path]:
    """Map each screen name to its collector's __init__.py, without importing anything.

    Importing waits until a screen is known to be enabled, so a disabled screen's
    dependencies never need to be installed.
    """
    return {init.parent.parent.name: init for init in sorted(screens_dir.glob("*/collector/__init__.py"))}


def load_screen(name: str, init: Path) -> Screen:
    """Import one screen's collector. Raises ModuleNotFoundError if its dependencies are missing."""
    module = _load(name, init)
    return Screen(module.collect, getattr(module, "INTERVAL_MINUTES", None))


def discover_screens(screens_dir: Path = SCREENS_DIR) -> dict[str, Screen]:
    """Load every screen, enabled or not. Tests use this to register the screen packages."""
    return {name: load_screen(name, init) for name, init in find_screens(screens_dir).items()}


def _load(name: str, init: Path):
    # Every screen's package is called "collector", so give each a unique module name.
    module_name = f"trmnl_screens.{name}.collector"
    # Relative imports inside the package resolve through these parents, so they must exist.
    for parent in ("trmnl_screens", f"trmnl_screens.{name}"):
        if parent not in sys.modules:
            sys.modules[parent] = types.ModuleType(parent)
            sys.modules[parent].__path__ = []
    spec = importlib.util.spec_from_file_location(
        module_name, init, submodule_search_locations=[str(init.parent)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
