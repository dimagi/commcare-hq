"""Shim: pillowtop.migrations.0007_copy_xforms_checkpoint has moved to corehq.apps.pillowtop.migrations.0007_copy_xforms_checkpoint."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations.0007_copy_xforms_checkpoint')
sys.modules[__name__] = _module
