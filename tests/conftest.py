"""Load benni_core_devices' HA-free files as a synthetic package."""

from __future__ import annotations

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "custom_components", "benni_core_devices")

pkg_name = "bcd_pure_pkg"
pkg = types.ModuleType(pkg_name)
pkg.__path__ = [PKG_DIR]
sys.modules[pkg_name] = pkg


def _load(modname: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"{pkg_name}.{modname}", os.path.join(PKG_DIR, filename)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{pkg_name}.{modname}"] = mod
    spec.loader.exec_module(mod)
    return mod


# Reihenfolge wichtig: const → device_types → logic → attributes/combined.
const = _load("const", "const.py")
device_types = _load("device_types", "device_types.py")
logic = _load("logic", "logic.py")
attributes = _load("attributes", "attributes.py")
combined = _load("combined", "combined.py")
agent_spec = _load("agent_spec", "agent_spec.py")

sys.modules["bcd_const"] = const
sys.modules["bcd_device_types"] = device_types
sys.modules["bcd_logic"] = logic
sys.modules["bcd_attributes"] = attributes
sys.modules["bcd_combined"] = combined
sys.modules["bcd_agent_spec"] = agent_spec
