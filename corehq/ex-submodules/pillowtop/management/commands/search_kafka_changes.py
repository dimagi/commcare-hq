"""Shim: pillowtop.management.commands.search_kafka_changes has moved to corehq.apps.pillowtop.management.commands.search_kafka_changes."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.search_kafka_changes')
sys.modules[__name__] = _module
