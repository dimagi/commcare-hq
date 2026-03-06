"""Shim: pillowtop.reindexer has moved to corehq.apps.pillowtop.reindexer."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.reindexer')
sys.modules[__name__] = _module
