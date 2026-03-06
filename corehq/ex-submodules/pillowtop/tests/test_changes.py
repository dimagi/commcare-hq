"""Shim: pillowtop.tests.test_changes has moved to corehq.apps.pillowtop.tests.test_changes."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_changes')
sys.modules[__name__] = _module
