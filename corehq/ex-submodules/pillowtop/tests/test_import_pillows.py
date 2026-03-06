"""Shim: pillowtop.tests.test_import_pillows has moved to corehq.apps.pillowtop.tests.test_import_pillows."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_import_pillows')
sys.modules[__name__] = _module
