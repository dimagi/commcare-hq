"""Shim: pillowtop.couchdb has moved to corehq.apps.pillowtop.couchdb."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.couchdb')
sys.modules[__name__] = _module
