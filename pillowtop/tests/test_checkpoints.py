from abc import ABCMeta, abstractproperty
from django.test import SimpleTestCase, override_settings, TestCase
import time
from dimagi.utils.decorators.memoized import memoized
from pillowtop.checkpoints.manager import PillowCheckpointManager, PillowCheckpoint
from pillowtop.checkpoints.util import get_machine_id
from pillowtop.dao.django import DjangoDocumentStore
from pillowtop.dao.mock import MockDocumentStore
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.models import DjangoPillowCheckpoint


class PillowCheckpointTest(SimpleTestCase):
    def test_get_machine_id(self):
        # since this is machine dependent just ensure that this returns something
        # and doesn't crash
        self.assertTrue(bool(get_machine_id()))

    @override_settings(PILLOWTOP_MACHINE_ID='test-ptop')
    def test_get_machine_id_settings(self):
        self.assertEqual('test-ptop', get_machine_id())

    def test_checkpoint_id(self):
        checkpoint_id = 'test-checkpoint-id'
        self.assertEqual(checkpoint_id, PillowCheckpoint(MockDocumentStore(), checkpoint_id).checkpoint_id)


class PillowCheckpointDaoTestMixin(object):
    __metaclass__ = ABCMeta

    _checkpoint_id = 'test-checkpoint-id'

    @abstractproperty
    def dao(self):
        pass

    @property
    @memoized
    def checkpoint(self):
        return PillowCheckpoint(self.dao, self._checkpoint_id)

    def test_get_or_create_empty(self):
        checkpoint_manager = PillowCheckpointManager(MockDocumentStore())
        checkpoint, created = checkpoint_manager.get_or_create_checkpoint('some-id')
        self.assertEqual('0', checkpoint['seq'])
        self.assertTrue(bool(checkpoint['timestamp']))
        self.assertTrue(bool(created))

    def test_create_initial_checkpoint(self):
        checkpoint, created = self.checkpoint.get_or_create()
        self.assertEqual('0', checkpoint['seq'])
        self.assertTrue(bool(created))

    def test_db_changes_returned(self):
        self.checkpoint.get_or_create()
        self.dao.save_document(self._checkpoint_id, {'seq': '1'})
        checkpoint = self.checkpoint.get_or_create().document
        self.assertEqual('1', checkpoint['seq'])

    def test_verify_unchanged_ok(self):
        self.checkpoint.get_or_create()
        checkpoint = self.checkpoint.get_or_create(verify_unchanged=True).document
        self.assertEqual('0', checkpoint['seq'])

    def test_verify_unchanged_fail(self):
        self.checkpoint.get_or_create()
        self.dao.save_document(self._checkpoint_id, {'seq': '1'})
        with self.assertRaises(PillowtopCheckpointReset):
            self.checkpoint.get_or_create(verify_unchanged=True)

    def test_update(self):
        self.checkpoint.get_or_create()
        for seq in ['1', '5', '22']:
            self.checkpoint.update_to(seq)
            self.assertEqual(seq, self.checkpoint.get_or_create().document['seq'])

    def test_update_verify_unchanged_fail(self):
        self.checkpoint.get_or_create()
        self.dao.save_document(self._checkpoint_id, {'seq': '1'})
        with self.assertRaises(PillowtopCheckpointReset):
            self.checkpoint.update_to('2')

    def test_touch_checkpoint_noop(self):
        checkpoint, created = self.checkpoint.get_or_create()
        self.assertTrue(created)
        first_checkpoint, created = self.checkpoint.get_or_create()
        self.assertFalse(created)
        self.checkpoint.touch(min_interval=10)
        second_checkpoint, created = self.checkpoint.get_or_create()
        self.assertFalse(created)
        self.assertEqual(first_checkpoint['timestamp'], second_checkpoint['timestamp'])

    def test_touch_checkpoint_update(self):
        timestamp = self.checkpoint.get_or_create().document['timestamp']
        time.sleep(.1)
        self.checkpoint.touch(min_interval=0)
        timestamp_back = self.checkpoint.get_or_create().document['timestamp']
        self.assertNotEqual(timestamp_back, timestamp)


class SimplePillowCheckpointDaoTest(SimpleTestCase, PillowCheckpointDaoTestMixin):

    @property
    @memoized
    def dao(self):
        return MockDocumentStore()


class SQLPillowCheckpointDaoTest(TestCase, PillowCheckpointDaoTestMixin):

    @property
    @memoized
    def dao(self):
        return DjangoDocumentStore(
            DjangoPillowCheckpoint, DjangoPillowCheckpoint.to_dict, DjangoPillowCheckpoint.from_dict,
        )
