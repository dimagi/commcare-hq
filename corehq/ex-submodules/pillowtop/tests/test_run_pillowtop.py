"""Shim: pillowtop.tests.test_run_pillowtop has moved to corehq.apps.pillowtop.tests.test_run_pillowtop."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_run_pillowtop')
sys.modules[__name__] = _module
