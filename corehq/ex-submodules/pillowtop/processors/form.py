"""Shim: pillowtop.processors.form has moved to corehq.apps.pillowtop.processors.form."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.processors.form')
sys.modules[__name__] = _module
