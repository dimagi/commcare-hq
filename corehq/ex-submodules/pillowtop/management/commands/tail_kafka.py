"""Shim: pillowtop.management.commands.tail_kafka has moved to corehq.apps.pillowtop.management.commands.tail_kafka."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.tail_kafka')
sys.modules[__name__] = _module
