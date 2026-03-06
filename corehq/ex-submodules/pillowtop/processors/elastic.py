"""Shim: pillowtop.processors.elastic has moved to corehq.apps.pillowtop.processors.elastic."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.processors.elastic')
sys.modules[__name__] = _module
