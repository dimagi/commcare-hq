"""Shim: pillowtop.reindexer.reindexer has moved to corehq.apps.pillowtop.reindexer.reindexer."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.reindexer.reindexer')
sys.modules[__name__] = _module
