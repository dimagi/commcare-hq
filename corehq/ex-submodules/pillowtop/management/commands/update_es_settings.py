"""Shim: pillowtop.management.commands.update_es_settings has moved to corehq.apps.pillowtop.management.commands.update_es_settings."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.update_es_settings')
sys.modules[__name__] = _module
