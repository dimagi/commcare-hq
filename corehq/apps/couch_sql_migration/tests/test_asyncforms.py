from django.test import SimpleTestCase

import attr

from .. import asyncforms as mod
from ..statedb import StateDB


class TestAsyncFormProcessor(SimpleTestCase):

    def test_pool_spawn_block_in_finish_processing_queues(self):
        def migrate_form(form, case_ids):
            print(f"migrating {form}")
            migrated.append(form)

        def add(form, queue):
            temp = Form(-form.form_id)
            assert queue.queues.try_obj(form.case_ids, temp), temp
            assert not queue.queues.try_obj(form.case_ids, form), form
            queue.queues.release_lock(temp)

        forms = [Form(n) for n in range(1, mod.POOL_SIZE * 3 + 1)]
        migrated = []
        statedb = StateDB.init(":memory:")
        with mod.AsyncFormProcessor(statedb, migrate_form) as queue:
            for form in forms:
                add(form, queue)
            # queue is loaded with 3x POOL_SIZE forms
            # pool.spawn(...) will block in _finish_processing_queues

        self.assertEqual(migrated, forms)
        unprocessed = statedb.pop_resume_state(type(queue).__name__, None)
        self.assertEqual(unprocessed, [])


class TestLockingQueues(SimpleTestCase):

    def setUp(self):
        self.queues = mod.PartiallyLockingQueue("id", max_size=-1)

    def _add_to_queues(self, queue_obj_id, lock_ids):
        self._add_item(lock_ids, DummyObject(queue_obj_id))
        self._check_queue_dicts(queue_obj_id, lock_ids, -1)

    def _add_item(self, lock_ids, obj):
        locked = self.queues._set_lock(lock_ids)
        self.queues.try_obj(lock_ids, obj)
        if locked:
            self.queues.currently_locked.difference_update(lock_ids)

    def _check_queue_dicts(self, queue_obj_id, lock_ids, location=None, present=True):
        """
        if location is None, it looks anywhere. If it is an int, it'll look in that spot
        present determines whether it's expected to be in the queue_by_lock_id or not
        """
        for lock_id in lock_ids:
            queue = self.queues.queue_by_lock_id[lock_id]
            if location is not None:
                self.assertEqual(present, queue_obj_id == queue[location])
            else:
                self.assertEqual(present, queue_obj_id in queue)
        if present:
            self.assertItemsEqual(lock_ids, self.queues.objs_by_queue_id[queue_obj_id][1])
        else:
            self.assertNotIn(queue_obj_id, self.queues.objs_by_queue_id)

    def _check_locks(self, lock_ids, lock_set=True):
        self.assertEqual(lock_set, self.queues._is_any_locked(lock_ids))

    def test_has_next(self):
        self.assertFalse(self.queues)
        self._add_to_queues('monadnock', ['heady_topper', 'sip_of_sunshine', 'focal_banger'])
        self.assertTrue(self.queues)

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
        self._check_queue_dicts('lafayette', final_lock_ids, location=-1)
        self._check_locks(['grapefruit_sculpin'], lock_set=True)
        self._check_locks(['wrought_iron'], lock_set=False)

    def test_try_obj_should_make_obj_wait_in_line(self):
        tiger = DummyObject('tiger')
        beaver = DummyObject('beaver')
        monkey = DummyObject('monkey')
        self.assertTrue(self.queues.try_obj(["tooth", "claw"], tiger))
        self.assertFalse(self.queues.try_obj(["tooth", "tail"], beaver))
        self.assertFalse(self.queues.try_obj(["tail"], monkey))
        self.queues.release_lock(tiger)
        self.assertEqual(self.queues.pop()[0], beaver)
        self.assertEqual(self.queues.pop()[0], None)
        self.queues.release_lock(beaver)
        self.assertEqual(self.queues.pop()[0], monkey)

    def test_pop(self):
        # nothing returned if nothing in queues
        self.assertEqual((None, None), self.queues.pop())

        # first obj in queues will be returned if nothing blocking
        lock_ids = ['old_chub', 'dales_pale', 'little_yella']
        queue_obj_id = 'moosilauke'
        self._add_to_queues(queue_obj_id, lock_ids)
        self.assertEqual(queue_obj_id, self.queues.pop()[0].id)
        self._check_locks(lock_ids, lock_set=True)

        # next object will not be returned if anything locks are held
        new_lock_ids = ['old_chub', 'ten_fidy']
        new_queue_obj_id = 'flume'
        self._add_to_queues(new_queue_obj_id, new_lock_ids)
        self.assertEqual((None, None), self.queues.pop())
        self._check_locks(['ten_fidy'], lock_set=False)

        # next object will not be returned if not first in all queues
        next_lock_ids = ['ten_fidy', 'death_by_coconut']
        next_queue_obj_id = 'liberty'
        self._add_to_queues(next_queue_obj_id, next_lock_ids)
        self.assertEqual((None, None), self.queues.pop())
        self._check_locks(next_lock_ids, lock_set=False)

        # will return something totally orthogonal though
        final_lock_ids = ['fugli', 'pinner']
        final_queue_obj_id = 'sandwich'
        self._add_to_queues(final_queue_obj_id, final_lock_ids)
        self.assertEqual(final_queue_obj_id, self.queues.pop()[0].id)
        self._check_locks(final_lock_ids)

    def test_release_lock(self):
        queue_obj = DummyObject('kancamagus')
        lock_ids = ['rubaeus', 'dirty_bastard', 'red\'s_rye']
        self._check_locks(lock_ids, lock_set=False)
        self.assertTrue(self.queues.try_obj(lock_ids, queue_obj))
        self.assertFalse(self.queues)
        self._check_locks(lock_ids, lock_set=True)
        self.queues.release_lock(queue_obj)
        self._check_locks(lock_ids, lock_set=False)

    def test_release_lock_with_no_locks(self):
        obj = DummyObject('blanch')
        self.assertTrue(self.queues.try_obj([], obj))
        self.assertFalse(self.queues)

    def test_try_obj_should_not_create_queues_unnecessarily(self):
        obj = DummyObject('beaver')
        self.assertTrue(self.queues.try_obj(["tooth", "tail"], obj))
        self.assertFalse(self.queues.queue_by_lock_id)

    def test_pop_should_discard_empty_queues(self):
        tiger = DummyObject('tiger')
        beaver = DummyObject('beaver')
        self.assertTrue(self.queues.try_obj(["tooth", "claw"], tiger))
        self.assertFalse(self.queues.try_obj(["tooth", "tail"], beaver))
        self.assertEqual(self.queues.pop(), (None, None))
        self.assertTrue(self.queues)
        self.queues.release_lock(tiger)
        obj, lock_ids = self.queues.pop()
        self.assertEqual(obj, beaver)
        self.assertFalse(self.queues.queue_by_lock_id)

    def test_max_size(self):
        self.assertEqual(-1, self.queues.max_size)
        self.assertFalse(self.queues.full)  # not full when no max size set
        self.queues.max_size = 2  # set max_size
        lock_ids = ['dali', 'manet', 'monet']
        queue_obj = DummyObject('osceola')
        self._add_item(lock_ids, queue_obj)
        self.assertFalse(self.queues.full)  # not full when not full
        queue_obj = DummyObject('east osceola')
        self._add_item(lock_ids, queue_obj)
        self.assertTrue(self.queues.full)  # full when full
        queue_obj = DummyObject('west osceola')
        self._add_item(lock_ids, queue_obj)
        self.assertTrue(self.queues.full)  # full when over full

    def test_queue_ids(self):
        tiger = DummyObject('tiger')
        beaver = DummyObject('beaver')
        self.assertTrue(self.queues.try_obj(["tooth", "claw"], tiger))
        self.assertFalse(self.queues.try_obj(["tooth", "tail"], beaver))
        self.assertEqual(self.queues.queue_ids, ["tiger", "beaver"])


@attr.s
class DummyObject(object):
    id = attr.ib()


@attr.s
class Form(object):
    form_id = attr.ib()

    @property
    def case_ids(self):
        return {self.form_id}
