"""Shim: pillowtop.management.commands.ptop_run_docs has moved to corehq.apps.pillowtop.management.commands.ptop_run_docs."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.ptop_run_docs')
sys.modules[__name__] = _module
