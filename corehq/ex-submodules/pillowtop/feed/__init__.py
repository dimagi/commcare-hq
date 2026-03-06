"""Shim: pillowtop.feed has moved to corehq.apps.pillowtop.feed."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.feed')
sys.modules[__name__] = _module
