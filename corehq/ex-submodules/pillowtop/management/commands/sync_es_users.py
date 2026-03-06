"""Shim: pillowtop.management.commands.sync_es_users has moved to corehq.apps.pillowtop.management.commands.sync_es_users."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.sync_es_users')
sys.modules[__name__] = _module
