"""Shim: pillowtop.feed.interface has moved to corehq.apps.pillowtop.feed.interface."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.feed.interface')
sys.modules[__name__] = _module
