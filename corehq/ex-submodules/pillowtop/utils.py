"""Shim: pillowtop.utils has moved to corehq.apps.pillowtop.utils."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.utils')
sys.modules[__name__] = _module
