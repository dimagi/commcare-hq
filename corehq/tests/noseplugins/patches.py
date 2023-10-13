from nose.plugins import Plugin

from corehq.apps.domain.tests.test_utils import patch_domain_deletion
from corehq.form_processor.tests.utils import patch_testcase_databases
from corehq.util.es.testing import patch_es_user_signals
from corehq.util.test_utils import patch_foreign_value_caches


class PatchesPlugin(Plugin):
    """Patches various things before tests are run"""
    name = "patches"
    enabled = True

    def options(self, parser, env):
        """Do not call super (always enabled)"""

    def begin(self):
        patch_assertItemsEqual()
        patch_testcase_databases()
        extend_freezegun_ignore_list()
        patch_es_user_signals()
        patch_foreign_value_caches()
        patch_domain_deletion()


def patch_assertItemsEqual():
    import unittest
    unittest.TestCase.assertItemsEqual = unittest.TestCase.assertCountEqual


GLOBAL_FREEZEGUN_IGNORE_LIST = ["kafka."]


def extend_freezegun_ignore_list():
    """Extend the freezegun ignore list"""
    import freezegun

    freezegun.configure(extend_ignore_list=GLOBAL_FREEZEGUN_IGNORE_LIST)
