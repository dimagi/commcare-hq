from __future__ import absolute_import
from __future__ import unicode_literals

import attr
from django.test import SimpleTestCase

from ..asyncforms import PartiallyLockingQueue


class TestLockingQueues(SimpleTestCase):

    def setUp(self):
        self.queues = PartiallyLockingQueue("id", max_size=-1)

    def _add_to_queues(self, queue_obj_id, lock_ids):
        self.queues._add_item(lock_ids, DummyObject(queue_obj_id))
        self._check_queue_dicts(queue_obj_id, lock_ids, -1)

    def _check_queue_dicts(self, queue_obj_id, lock_ids, location=None, present=True):
        """
        if location is None, it looks anywhere. If it is an int, it'll look in that spot
        present determines whether it's expected to be in the queue_by_lock_id or not
        """
        for lock_id in lock_ids:
            queue = self.queues.queue_by_lock_id[lock_id]
            if location is not None:
                self.assertEqual(
                    present,
                    len(queue) > location - 1 and queue_obj_id == queue[location],
                )
            else:
                self.assertEqual(present, queue_obj_id in queue)

        self.assertItemsEqual(lock_ids, self.queues.lock_ids_by_queue_id[queue_obj_id])

    def _check_locks(self, lock_ids, lock_set=True):
        self.assertEqual(lock_set, self.queues._check_lock(lock_ids))

    def test_has_next(self):
        self.assertFalse(self.queues.has_next())
        self._add_to_queues('monadnock', ['heady_topper', 'sip_of_sunshine', 'focal_banger'])
        self.assertTrue(self.queues.has_next())

    def test_try_obj(self):
        # first object is fine
        lock_ids = ['grapefruit_sculpin', '60_minute', 'boom_sauce']
        queue_obj = DummyObject('little_haystack')
        self.assertTrue(self.queues.try_obj(lock_ids, queue_obj))
        self._check_locks(lock_ids, lock_set=True)
        self._check_queue_dicts('little_haystack', lock_ids, present=False)

        # following objects without overlapping locks are fine
        new_lock_ids = ['brew_free', 'steal_this_can']
        new_queue_obj = DummyObject('lincoln')
        self.assertTrue(self.queues.try_obj(new_lock_ids, new_queue_obj))
        self._check_locks(new_lock_ids, lock_set=True)
        self._check_queue_dicts('lincoln', new_lock_ids, present=False)

        # following ojbects with overlapping locks add to queue
        final_lock_ids = ['grapefruit_sculpin', 'wrought_iron']
        final_queue_obj = DummyObject('lafayette')
        self.assertFalse(self.queues.try_obj(final_lock_ids, final_queue_obj))
        self._check_queue_dicts('lafayette', final_lock_ids, -1)
        self._check_locks(['grapefruit_sculpin'], lock_set=True)
        self._check_locks(['wrought_iron'], lock_set=False)

    def test_get_next(self):
        # nothing returned if nothing in queues
        self.assertEqual((None, None), self.queues.get_next())

        # first obj in queues will be returned if nothing blocking
        lock_ids = ['old_chub', 'dales_pale', 'little_yella']
        queue_obj_id = 'moosilauke'
        self._add_to_queues(queue_obj_id, lock_ids)
        self.assertEqual(queue_obj_id, self.queues.get_next()[0].id)
        self._check_locks(lock_ids, lock_set=True)

        # next object will not be returned if anything locks are held
        new_lock_ids = ['old_chub', 'ten_fidy']
        new_queue_obj_id = 'flume'
        self._add_to_queues(new_queue_obj_id, new_lock_ids)
        self.assertEqual((None, None), self.queues.get_next())
        self._check_locks(['ten_fidy'], lock_set=False)

        # next object will not be returned if not first in all queues
        next_lock_ids = ['ten_fidy', 'death_by_coconut']
        next_queue_obj_id = 'liberty'
        self._add_to_queues(next_queue_obj_id, next_lock_ids)
        self.assertEqual((None, None), self.queues.get_next())
        self._check_locks(next_lock_ids, lock_set=False)

        # will return something totally orthogonal though
        final_lock_ids = ['fugli', 'pinner']
        final_queue_obj_id = 'sandwich'
        self._add_to_queues(final_queue_obj_id, final_lock_ids)
        self.assertEqual(final_queue_obj_id, self.queues.get_next()[0].id)
        self._check_locks(final_lock_ids)

    def test_release_locks(self):
        lock_ids = ['rubaeus', 'dirty_bastard', 'red\'s_rye']
        self._check_locks(lock_ids, lock_set=False)
        self.queues._set_lock(lock_ids)
        self._check_locks(lock_ids, lock_set=True)
        self.queues._release_lock(lock_ids)
        self._check_locks(lock_ids, lock_set=False)

        queue_obj = DummyObject('kancamagus')
        self.queues._add_item(lock_ids, queue_obj, to_queue=False)
        self.queues._set_lock(lock_ids)
        self._check_locks(lock_ids, lock_set=True)
        self.queues.release_lock_for_queue_obj(queue_obj)
        self._check_locks(lock_ids, lock_set=False)

    def test_max_size(self):
        self.assertEqual(-1, self.queues.max_size)
        self.assertFalse(self.queues.full)  # not full when no max size set
        self.queues.max_size = 2  # set max_size
        lock_ids = ['dali', 'manet', 'monet']
        queue_obj = DummyObject('osceola')
        self.queues._add_item(lock_ids, queue_obj)
        self.assertFalse(self.queues.full)  # not full when not full
        queue_obj = DummyObject('east osceola')
        self.queues._add_item(lock_ids, queue_obj)
        self.assertTrue(self.queues.full)  # full when full
        queue_obj = DummyObject('west osceola')
        self.queues._add_item(lock_ids, queue_obj)
        self.assertTrue(self.queues.full)  # full when over full


@attr.s
class DummyObject(object):

    id = attr.ib()
