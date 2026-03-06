"""Shim: pillowtop.reindexer.change_providers.case has moved to corehq.apps.pillowtop.reindexer.change_providers.case."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.reindexer.change_providers.case')
sys.modules[__name__] = _module
