"""Shim: pillowtop.tests.test_utils has moved to corehq.apps.pillowtop.tests.test_utils."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_utils')
sys.modules[__name__] = _module
