"""Shim: pillowtop.processors has moved to corehq.apps.pillowtop.processors."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.processors')
sys.modules[__name__] = _module
