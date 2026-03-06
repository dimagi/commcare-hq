"""Shim: pillowtop.migrations.0001_initial has moved to corehq.apps.pillowtop.migrations.0001_initial."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations.0001_initial')
sys.modules[__name__] = _module
