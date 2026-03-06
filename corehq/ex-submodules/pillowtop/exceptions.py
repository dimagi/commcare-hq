"""Shim: pillowtop.exceptions has moved to corehq.apps.pillowtop.exceptions."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.exceptions')
sys.modules[__name__] = _module
