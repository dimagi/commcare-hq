"""Shim: pillowtop.reindexer.change_providers.composite has moved to corehq.apps.pillowtop.reindexer.change_providers.composite."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.reindexer.change_providers.composite')
sys.modules[__name__] = _module
