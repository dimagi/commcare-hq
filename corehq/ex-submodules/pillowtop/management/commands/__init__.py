"""Shim: pillowtop.management.commands has moved to corehq.apps.pillowtop.management.commands."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands')
sys.modules[__name__] = _module
