"""Shim: pillowtop.migrations.0005_kafkacheckpoint_doc_modification_time has moved to corehq.apps.pillowtop.migrations.0005_kafkacheckpoint_doc_modification_time."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations.0005_kafkacheckpoint_doc_modification_time')
sys.modules[__name__] = _module
