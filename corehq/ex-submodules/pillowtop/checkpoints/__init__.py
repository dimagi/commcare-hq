"""Shim: pillowtop.checkpoints has moved to corehq.apps.pillowtop.checkpoints."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.checkpoints')
sys.modules[__name__] = _module
