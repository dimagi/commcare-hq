"""Shim: pillowtop.dao.mock has moved to corehq.apps.pillowtop.dao.mock."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.dao.mock')
sys.modules[__name__] = _module
