"""Shim: pillowtop.processors.interface has moved to corehq.apps.pillowtop.processors.interface."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.processors.interface')
sys.modules[__name__] = _module
