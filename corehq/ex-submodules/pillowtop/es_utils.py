"""Shim: pillowtop.es_utils has moved to corehq.apps.pillowtop.es_utils."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.es_utils')
sys.modules[__name__] = _module
