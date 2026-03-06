"""Shim: pillowtop has moved to corehq.apps.pillowtop."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop')
sys.modules[__name__] = _module
