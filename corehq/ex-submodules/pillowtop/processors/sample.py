"""Shim: pillowtop.processors.sample has moved to corehq.apps.pillowtop.processors.sample."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.processors.sample')
sys.modules[__name__] = _module
