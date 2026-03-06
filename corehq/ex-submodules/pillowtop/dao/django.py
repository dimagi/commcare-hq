"""Shim: pillowtop.dao.django has moved to corehq.apps.pillowtop.dao.django."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.dao.django')
sys.modules[__name__] = _module
