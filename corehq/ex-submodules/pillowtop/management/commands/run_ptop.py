"""Shim: pillowtop.management.commands.run_ptop has moved to corehq.apps.pillowtop.management.commands.run_ptop."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.run_ptop')
sys.modules[__name__] = _module
