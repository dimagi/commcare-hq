"""Shim: pillowtop.models has moved to corehq.apps.pillowtop.models."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.models')
sys.modules[__name__] = _module
