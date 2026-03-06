"""Shim: pillowtop.management.commands.ptop_reset_checkpoint has moved to corehq.apps.pillowtop.management.commands.ptop_reset_checkpoint."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.ptop_reset_checkpoint')
sys.modules[__name__] = _module
