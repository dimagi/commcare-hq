"""Shim: pillowtop.dao.interface has moved to corehq.apps.pillowtop.dao.interface."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.dao.interface')
sys.modules[__name__] = _module
