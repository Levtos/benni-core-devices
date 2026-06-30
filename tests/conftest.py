"""Load benni_core_devices' HA-free files as a synthetic package."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "custom_components", "benni_core_devices")

pkg_name = "bcd_pure_pkg"
pkg = types.ModuleType(pkg_name)
pkg.__path__ = [PKG_DIR]
sys.modules[pkg_name] = pkg

try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    yaml_shim = types.ModuleType("yaml")

    class YAMLError(ValueError):
        pass

    def safe_load(raw):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as err:
            raise YAMLError(str(err)) from err

    def safe_dump(data, sort_keys=False, allow_unicode=True):
        return json.dumps(data, sort_keys=sort_keys, ensure_ascii=not allow_unicode, indent=2)

    yaml_shim.YAMLError = YAMLError
    yaml_shim.safe_load = safe_load
    yaml_shim.safe_dump = safe_dump
    sys.modules["yaml"] = yaml_shim


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
slot_reader = _load("slot_reader", "slot_reader.py")
attributes = _load("attributes", "attributes.py")
combined_expr = _load("combined_expr", "combined_expr.py")
combined = _load("combined", "combined.py")
bulk_import = _load("bulk_import", "bulk_import.py")
contract_catalog = _load("contract_catalog", "contract_catalog.py")
raw_entity_catalog = _load("raw_entity_catalog", "raw_entity_catalog.py")
agent_spec = _load("agent_spec", "agent_spec.py")

sys.modules["bcd_const"] = const
sys.modules["bcd_device_types"] = device_types
sys.modules["bcd_logic"] = logic
sys.modules["bcd_slot_reader"] = slot_reader
sys.modules["bcd_attributes"] = attributes
sys.modules["bcd_combined_expr"] = combined_expr
sys.modules["bcd_combined"] = combined
sys.modules["bcd_bulk_import"] = bulk_import
sys.modules["bcd_contract_catalog"] = contract_catalog
sys.modules["bcd_raw_entity_catalog"] = raw_entity_catalog
sys.modules["bcd_agent_spec"] = agent_spec
