"""Shim: pillowtop.tests has moved to corehq.apps.pillowtop.tests."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests')
sys.modules[__name__] = _module
