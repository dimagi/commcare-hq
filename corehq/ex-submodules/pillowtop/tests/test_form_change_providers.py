"""Shim: pillowtop.tests.test_form_change_providers has moved to corehq.apps.pillowtop.tests.test_form_change_providers."""
import sys
import importlib
_module = importlib.import_module('corehq.apps.pillowtop.tests.test_form_change_providers')
sys.modules[__name__] = _module
