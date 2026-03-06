"""Shim: pillowtop.tests.test_bulk has moved to corehq.apps.pillowtop.tests.test_bulk."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_bulk')
sys.modules[__name__] = _module
