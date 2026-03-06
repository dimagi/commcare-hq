"""Shim: pillowtop.checkpoints.manager has moved to corehq.apps.pillowtop.checkpoints.manager."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.checkpoints.manager')
sys.modules[__name__] = _module
