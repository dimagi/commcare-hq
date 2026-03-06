"""Shim: pillowtop.tests.test_elasticsearch has moved to corehq.apps.pillowtop.tests.test_elasticsearch."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_elasticsearch')
sys.modules[__name__] = _module
