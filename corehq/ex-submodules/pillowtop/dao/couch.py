"""Shim: pillowtop.dao.couch has moved to corehq.apps.pillowtop.dao.couch."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.dao.couch')
sys.modules[__name__] = _module
