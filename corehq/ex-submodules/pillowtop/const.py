"""Shim: pillowtop.const has moved to corehq.apps.pillowtop.const."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.const')
sys.modules[__name__] = _module
