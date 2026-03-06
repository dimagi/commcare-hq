"""Shim: pillowtop.pillow.interface has moved to corehq.apps.pillowtop.pillow.interface."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.pillow.interface')
sys.modules[__name__] = _module
