"""Shim: pillowtop.management.commands.split_pillow_checkpoints has moved to corehq.apps.pillowtop.management.commands.split_pillow_checkpoints."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.management.commands.split_pillow_checkpoints')
sys.modules[__name__] = _module
