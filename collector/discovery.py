"""Finds the screens under screens/ that have a collector package, and loads them one at a time."""

import functools
import importlib.util
import os
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

Collect = Callable[[], dict[str, Any]]
# Given the payload just collected, the minutes until the screen's next run, or None for its interval.
NextRun = Callable[[dict[str, Any]], float | None]

SCREENS_DIR = Path(__file__).resolve().parent.parent / "screens"


@dataclass(frozen=True)
class Screen:
    collect: Collect
    # The screen's own default, from INTERVAL_MINUTES in its collector package.
    interval_minutes: int | None = None
    # MERGE_STRATEGY in its collector package; None replaces the stored data on each push.
    merge_strategy: str | None = None
    # next_run_minutes(payload) in its collector package, to run sooner than its interval.
    next_run_minutes: NextRun | None = None


def find_screens(screens_dir: Path = SCREENS_DIR, env: Mapping[str, str] | None = None) -> dict[str, Path]:
    """Map each screen name to its collector's __init__.py, without importing anything.

    Importing waits until a screen is known to be enabled, so a disabled screen's
    dependencies never need to be installed. A screen listed in <SCREEN>_INSTANCES
    (e.g. BULL_OR_BEAR_INSTANCES=aapl,msft) runs once per instance, as "<screen>-<instance>",
    each with its own webhook and interval settings.
    """
    env = os.environ if env is None else env
    found = {}
    for init in sorted(screens_dir.glob("*/collector/__init__.py")):
        name = init.parent.parent.name
        instances = [i.strip().lower() for i in env.get(f"{name.replace('-', '_').upper()}_INSTANCES", "").split(",") if i.strip()]
        for key in [f"{name}-{i}" for i in instances] or [name]:
            found[key] = init
    return found


def load_screen(name: str, init: Path) -> Screen:
    """Import one screen's collector. Raises ModuleNotFoundError if its dependencies are missing.

    An instance name ("<screen>-<instance>") gets the screen's collect with instance= bound.
    """
    screen = init.parent.parent.name
    module = _load(screen, init)
    instance = name[len(screen) + 1:]
    return Screen(
        functools.partial(module.collect, instance=instance) if instance else module.collect,
        getattr(module, "INTERVAL_MINUTES", None),
        getattr(module, "MERGE_STRATEGY", None),
        getattr(module, "next_run_minutes", None),
    )


def discover_screens(screens_dir: Path = SCREENS_DIR) -> dict[str, Screen]:
    """Load every screen, enabled or not. Tests use this to register the screen packages."""
    return {name: load_screen(name, init) for name, init in find_screens(screens_dir).items()}


def _load(name: str, init: Path):
    # Every screen's package is called "collector", so give each a unique module name.
    module_name = f"trmnl_screens.{name}.collector"
    loaded = sys.modules.get(module_name)
    if loaded is not None and getattr(loaded, "__file__", None) == str(init):  # instances share one import
        return loaded
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
