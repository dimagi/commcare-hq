"""Shim: pillowtop.migrations has moved to corehq.apps.pillowtop.migrations."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations')
sys.modules[__name__] = _module
