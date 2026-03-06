"""Shim: pillowtop.tests.utils has moved to corehq.apps.pillowtop.tests.utils."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.utils')
sys.modules[__name__] = _module
