"""Shim: pillowtop.tests.test_config has moved to corehq.apps.pillowtop.tests.test_config."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_config')
sys.modules[__name__] = _module
