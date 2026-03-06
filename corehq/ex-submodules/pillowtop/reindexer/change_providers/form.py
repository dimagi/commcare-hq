"""Shim: pillowtop.reindexer.change_providers.form has moved to corehq.apps.pillowtop.reindexer.change_providers.form."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.reindexer.change_providers.form')
sys.modules[__name__] = _module
