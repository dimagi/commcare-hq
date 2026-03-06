"""Shim: pillowtop.migrations.0006_add_geopoint_to_case_search_index has moved to corehq.apps.pillowtop.migrations.0006_add_geopoint_to_case_search_index."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.migrations.0006_add_geopoint_to_case_search_index')
sys.modules[__name__] = _module
