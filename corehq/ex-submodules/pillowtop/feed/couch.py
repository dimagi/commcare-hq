"""Shim: pillowtop.feed.couch has moved to corehq.apps.pillowtop.feed.couch."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.feed.couch')
sys.modules[__name__] = _module
