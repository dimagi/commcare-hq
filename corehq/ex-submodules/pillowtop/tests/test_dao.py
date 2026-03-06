"""Shim: pillowtop.tests.test_dao has moved to corehq.apps.pillowtop.tests.test_dao."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_dao')
sys.modules[__name__] = _module
