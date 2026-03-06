"""Shim: pillowtop.reindexer.change_providers.couch has moved to corehq.apps.pillowtop.reindexer.change_providers.couch."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.reindexer.change_providers.couch')
sys.modules[__name__] = _module
