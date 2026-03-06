"""Shim: pillowtop.tests.test_checkpoints has moved to corehq.apps.pillowtop.tests.test_checkpoints."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_checkpoints')
sys.modules[__name__] = _module
