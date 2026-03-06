"""Shim: pillowtop.migrations.0008_sync_es_with_couch_webusers has moved to corehq.apps.pillowtop.migrations.0008_sync_es_with_couch_webusers."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations.0008_sync_es_with_couch_webusers')
sys.modules[__name__] = _module
