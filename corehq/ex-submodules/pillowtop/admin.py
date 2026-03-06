"""Shim: pillowtop.admin has moved to corehq.apps.pillowtop.admin."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.admin')
sys.modules[__name__] = _module
