"""Shim: pillowtop.feed.mock has moved to corehq.apps.pillowtop.feed.mock."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.feed.mock')
sys.modules[__name__] = _module
