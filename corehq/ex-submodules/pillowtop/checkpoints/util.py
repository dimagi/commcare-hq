"""Shim: pillowtop.checkpoints.util has moved to corehq.apps.pillowtop.checkpoints.util."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.checkpoints.util')
sys.modules[__name__] = _module
