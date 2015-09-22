from django.conf import settings
from django.test import SimpleTestCase, override_settings
from pillowtop.checkpoints.manager import PillowCheckpointManager, PillowCheckpointManagerInstance
from pillowtop.checkpoints.util import get_machine_id
from pillowtop.dao.mock import MockDocumentStore
from pillowtop.exceptions import PillowtopCheckpointReset


class PillowCheckpointTest(SimpleTestCase):

    @override_settings(PILLOWTOP_MACHINE_ID='test-ptop')
    def test_get_machine_id_settings(self):
        self.assertEqual('test-ptop', get_machine_id())

    def test_get_machine_id(self):
        # since this is machine dependent just ensure that this returns something
        # and doesn't crash
        self.assertTrue(bool(get_machine_id()))

    def test_get_or_create_empty(self):
        checkpoint_manager = PillowCheckpointManager(MockDocumentStore())
        checkpoint = checkpoint_manager.get_or_create_checkpoint('some-id')
        self.assertEqual('0', checkpoint['seq'])


class PillowCheckpointManagerInstanceTest(SimpleTestCase):

    def setUp(self):
        self._checkpoint_id = 'test-checkpoint-id'
        self._dao = MockDocumentStore()
        self._manager = PillowCheckpointManagerInstance(self._dao, self._checkpoint_id)

    def test_checkpoint_id(self):
        self.assertEqual(self._checkpoint_id, self._manager.checkpoint_id)

    def test_create_initial_checkpoint(self):
        checkpoint = self._manager.get_or_create_checkpoint()
        self.assertEqual('0', checkpoint['seq'])

    def test_db_changes_returned(self):
        self._manager.get_or_create_checkpoint()
        self._dao.save_document(self._checkpoint_id, {'seq': '1'})
        checkpoint = self._manager.get_or_create_checkpoint()
        self.assertEqual('1', checkpoint['seq'])

    def test_verify_unchanged_ok(self):
        self._manager.get_or_create_checkpoint()
        checkpoint = self._manager.get_or_create_checkpoint(verify_unchanged=True)
        self.assertEqual('0', checkpoint['seq'])

    def test_verify_unchanged_fail(self):
        self._manager.get_or_create_checkpoint()
        self._dao.save_document(self._checkpoint_id, {'seq': '1'})
        with self.assertRaises(PillowtopCheckpointReset):
            self._manager.get_or_create_checkpoint(verify_unchanged=True)
