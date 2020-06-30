from nose.plugins import Plugin

from corehq.util.es.testing import patch_es_user_signals


class PatchesPlugin(Plugin):
    """Patches various things before tests are run"""
    name = "patches"
    enabled = True

    def options(self, parser, env):
        """Do not call super (always enabled)"""

    def begin(self):
        patch_assertItemsEqual()
        fix_freezegun_bugs()
        patch_es_user_signals()


def patch_assertItemsEqual():
    import unittest
    unittest.TestCase.assertItemsEqual = unittest.TestCase.assertCountEqual


GLOBAL_FREEZEGUN_IGNORE_LIST = ["kafka."]


def fix_freezegun_bugs():
    """Fix error in freezegun.api.freeze_time

    This error occurs in a background thread that is either triggered by
    a test using freezegun or becomes active while freezegun patches are
    in place.

    More complete error details:
    ```
    Exception in thread cchq-producer-network-thread:
    Traceback (most recent call last):
    ...
    freezegun/api.py", line 151, in _should_use_real_time
      if not ignore_lists[-1]:
    IndexError: list index out of range
    ```
    """
    import freezegun.api as api

    def freeze_time(*args, **kw):
        kw["ignore"] = kw.get("ignore", []) + GLOBAL_FREEZEGUN_IGNORE_LIST
        return real_freeze_time(*args, **kw)

    # add base ignore list to avoid index error
    assert not api.ignore_lists, f"expected empty list, got {api.ignore_lists}"
    api.ignore_lists.append(tuple(GLOBAL_FREEZEGUN_IGNORE_LIST))

    # patch freeze_time so it always ignores kafka
    real_freeze_time = api.freeze_time
    api.freeze_time = freeze_time
