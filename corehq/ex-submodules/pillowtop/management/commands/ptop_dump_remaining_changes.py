"""Shim: pillowtop.management.commands.ptop_dump_remaining_changes has moved to corehq.apps.pillowtop.management.commands.ptop_dump_remaining_changes."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.ptop_dump_remaining_changes')
sys.modules[__name__] = _module
