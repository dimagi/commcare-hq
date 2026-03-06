"""Shim: pillowtop.management.commands.add_kafka_partition has moved to corehq.apps.pillowtop.management.commands.add_kafka_partition."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.add_kafka_partition')
sys.modules[__name__] = _module
