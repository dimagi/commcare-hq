from django.test import SimpleTestCase
from threading import Thread
from corehq.apps.hqwebapp.utils.bootstrap import (
    get_bootstrap_version,
    set_bootstrap_version3,
    set_bootstrap_version5,
    clear_bootstrap_version,
    BOOTSTRAP_3,
    BOOTSTRAP_5,
)


class BootstrapThreadTests(SimpleTestCase):
    def setUp(self):
        self.addCleanup(clear_bootstrap_version)

    def test_no_explicit_version_defaults_to_bootstrap3(self):
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_3)

    def test_can_set_bootstrap3(self):
        set_bootstrap_version3()
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_3)

    def test_can_set_bootstrap5(self):
        set_bootstrap_version5()
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_5)

    def test_clear_bootstrap_version_removes_previous_setting(self):
        set_bootstrap_version5()
        clear_bootstrap_version()
        # Should default to bootstrap 3 when no explicit setting is found
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_3)

    def test_setting_is_local_to_thread(self):
        results = {}

        def get_version(results):
            results['thread'] = get_bootstrap_version()

        set_bootstrap_version5()
        thread = Thread(target=get_version, args=(results,))
        thread.start()
        thread.join()

        self.assertEqual(results['thread'], BOOTSTRAP_3)
