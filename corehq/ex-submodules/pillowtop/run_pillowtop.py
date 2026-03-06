"""Shim: pillowtop.run_pillowtop has moved to corehq.apps.pillowtop.run_pillowtop."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.run_pillowtop')
sys.modules[__name__] = _module
