"""Shim: pillowtop.tests.test_metrics has moved to corehq.apps.pillowtop.tests.test_metrics."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_metrics')
sys.modules[__name__] = _module
