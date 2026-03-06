"""Shim: pillowtop.logger has moved to corehq.apps.pillowtop.logger."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.logger')
sys.modules[__name__] = _module
