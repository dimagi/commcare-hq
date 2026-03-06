"""Shim: pillowtop.tests.test_couch has moved to corehq.apps.pillowtop.tests.test_couch."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_couch')
sys.modules[__name__] = _module
