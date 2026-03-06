"""Shim: pillowtop.tests.test_pillow has moved to corehq.apps.pillowtop.tests.test_pillow."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_pillow')
sys.modules[__name__] = _module
