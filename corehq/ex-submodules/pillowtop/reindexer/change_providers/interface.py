"""Shim: pillowtop.reindexer.change_providers.interface has moved to corehq.apps.pillowtop.reindexer.change_providers.interface."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.reindexer.change_providers.interface')
sys.modules[__name__] = _module
