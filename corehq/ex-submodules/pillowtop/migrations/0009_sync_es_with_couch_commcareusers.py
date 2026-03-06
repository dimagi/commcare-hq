"""Shim: pillowtop.migrations.0009_sync_es_with_couch_commcareusers has moved to corehq.apps.pillowtop.migrations.0009_sync_es_with_couch_commcareusers."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations.0009_sync_es_with_couch_commcareusers')
sys.modules[__name__] = _module
