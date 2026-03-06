"""Shim: pillowtop.migrations.0004_offset_to_big_int has moved to corehq.apps.pillowtop.migrations.0004_offset_to_big_int."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations.0004_offset_to_big_int')
sys.modules[__name__] = _module
