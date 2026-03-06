"""Shim: pillowtop.tasks has moved to corehq.apps.pillowtop.tasks."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tasks')
sys.modules[__name__] = _module
