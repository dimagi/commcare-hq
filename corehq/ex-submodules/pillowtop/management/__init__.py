"""Shim: pillowtop.management has moved to corehq.apps.pillowtop.management."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management')
sys.modules[__name__] = _module
