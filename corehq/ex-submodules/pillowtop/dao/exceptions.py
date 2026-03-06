"""Shim: pillowtop.dao.exceptions has moved to corehq.apps.pillowtop.dao.exceptions."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.dao.exceptions')
sys.modules[__name__] = _module
