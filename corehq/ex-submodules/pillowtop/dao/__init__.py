"""Shim: pillowtop.dao has moved to corehq.apps.pillowtop.dao."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.dao')
sys.modules[__name__] = _module
