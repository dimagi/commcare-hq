"""Shim: pillowtop.pillow has moved to corehq.apps.pillowtop.pillow."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.pillow')
sys.modules[__name__] = _module
