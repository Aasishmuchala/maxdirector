"""Enforce the hexagon boundary: importing the whole pure core must NOT pull in pymxs
(nor torch). If this fails, some core module reached across the boundary — fix the import.
"""

import importlib
import pkgutil
import sys

import maxdirector.core as core


def test_core_imports_no_pymxs_or_torch():
    for mod in pkgutil.walk_packages(core.__path__, prefix="maxdirector.core."):
        importlib.import_module(mod.name)
    assert "pymxs" not in sys.modules, "a core module imported pymxs"
    assert "torch" not in sys.modules, "a core module imported torch"
