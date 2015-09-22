from django.conf import settings
from django.test import SimpleTestCase, override_settings
from pillowtop.checkpoints.util import get_machine_id


class PillowCheckpointTest(SimpleTestCase):

    @override_settings(PILLOWTOP_MACHINE_ID='test-ptop')
    def test_get_machine_id_settings(self):
        self.assertEqual('test-ptop', get_machine_id())

    def test_get_machine_id(self):
        # since this is machine dependent just ensure that this returns something
        # and doesn't crash
        self.assertTrue(bool(get_machine_id()))
