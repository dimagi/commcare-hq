"""Shim: pillowtop.management.commands.create_checkpoints_for_merged_pillows has moved to corehq.apps.pillowtop.management.commands.create_checkpoints_for_merged_pillows."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.create_checkpoints_for_merged_pillows')
sys.modules[__name__] = _module
