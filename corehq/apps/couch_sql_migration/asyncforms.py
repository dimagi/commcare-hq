import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta

import gevent
from gevent.pool import Pool

from casexml.apps.case.xform import get_case_ids_from_form, get_case_updates
from couchforms.models import XFormInstance, XFormOperation
from dimagi.utils.chunked import chunked

from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import (
    PROBLEM_TEMPLATE_START,
)
from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.form_processor.exceptions import MissingFormXml

log = logging.getLogger(__name__)
POOL_SIZE = 15


class AsyncFormProcessor(object):

    def __init__(self, statedb, migrate_form):
        self.statedb = statedb
        self.migrate_form = migrate_form

    def __enter__(self):
        self.pool = Pool(POOL_SIZE)
        self.queues = PartiallyLockingQueue()
        form_ids = self.statedb.pop_resume_state(type(self).__name__, [])
        self._rebuild_queues(form_ids)
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        queue_ids = self.queues.queue_ids
        try:
            if exc_type is None:
                queue_ids = self._finish_processing_queues()
            else:
                self.pool.kill()  # stop workers -> reduce chaos in logs
        finally:
            key = type(self).__name__
            self.statedb.set_resume_state(key, queue_ids)
            log.info("saved %s state (%s ids)", key, len(queue_ids))
            self.queues = self.pool = None

    def _rebuild_queues(self, form_ids):
        for chunk in chunked(form_ids, 100, list):
            for form in FormAccessorCouch.get_forms(chunk):
                self._try_to_process_form(form)
        self._try_to_empty_queues()

    def process_xform(self, doc):
        """Process XFormInstance document asynchronously"""
        form_id = doc["_id"]
        log.debug('Processing doc: XFormInstance(%s)', form_id)
        if doc.get('problem'):
            if str(doc['problem']).startswith(PROBLEM_TEMPLATE_START):
                doc = _fix_replacement_form_problem_in_couch(doc)
            else:
                self.statedb.add_problem_form(form_id)
                return
        try:
            wrapped_form = XFormInstance.wrap(doc)
        except Exception:
            log.exception("Error migrating form %s", form_id)
            self.statedb.save_form_diffs(doc, {})
        else:
            self._try_to_process_form(wrapped_form)
            self._try_to_empty_queues()

    def _try_to_process_form(self, wrapped_form):
        case_ids = get_case_ids(wrapped_form)
        if self.queues.try_obj(case_ids, wrapped_form):
            self.pool.spawn(self._async_migrate_form, wrapped_form, case_ids)
        elif self.queues.full:
            gevent.sleep()  # swap greenlets

    def _async_migrate_form(self, wrapped_form, case_ids):
        try:
            self.migrate_form(wrapped_form, case_ids)
        finally:
            self.queues.release_lock(wrapped_form)

    def _try_to_empty_queues(self):
        while True:
            new_wrapped_form, case_ids = self.queues.pop()
            if not new_wrapped_form:
                break
            self.pool.spawn(self._async_migrate_form, new_wrapped_form, case_ids)

    def _finish_processing_queues(self):
        update_interval = timedelta(seconds=10)
        next_check = datetime.now()
        pool = self.pool
        while self.queues:
            wrapped_form, case_ids = self.queues.pop()
            if wrapped_form:
                pool.spawn(self._async_migrate_form, wrapped_form, case_ids)
            else:
                gevent.sleep()  # swap greenlets

            now = datetime.now()
            if now > next_check:
                log.info('Waiting on %s docs', len(self.queues) + len(pool))
                next_check += update_interval

        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))

        unprocessed = self.queues.queue_ids
        if unprocessed:
            log.error("Unprocessed forms (unexpected): %s", unprocessed)
        return unprocessed


class PartiallyLockingQueue(object):
    """ Data structure that holds a queue of objects returning them as locks become free

    This is not currently thread safe

    Interface:
    `.try_obj(lock_ids, queue_obj)` add a new object, seeing if it can be
        processed immediately
    `.pop()` get a locked object and lock_ids to be processed
    `bool(queue)` find out if there are still objects in the queue
    `len(queue)` get the number of objects in the queue
    `.release_lock(queoe_obj)` release the locks associated
        with an object once finished processing
    """

    def __init__(self, queue_id_param="form_id", max_size=10000):
        """
        :queue_id_param string: param of the queued objects to pull an id from
        :max_size int: the maximum size the queue should reach. -1 means no limit
        """
        self.queue_by_lock_id = defaultdict(deque)
        self.objs_by_queue_id = {}  # {queue_id: (obj, lock_ids), ...}
        self.processing = {}  # {queue_id: lock_ids, ...}
        self.currently_locked = set()
        self.max_size = max_size

        def get_queue_obj_id(queue_obj):
            return getattr(queue_obj, queue_id_param)
        self.get_queue_obj_id = get_queue_obj_id

    @property
    def queue_ids(self):
        """Return a list of queue object ids

        This includes all objects that are currently locked (processing)
        as well as all objects in the queue waiting to be processed.
        Queue state can be rebuilt using this list by looking up each
        queue object and lock ids and passing them to `try_obj()`.
        """
        return list(self.processing) + list(self.objs_by_queue_id)

    def try_obj(self, lock_ids, queue_obj):
        """ Checks if the object can acquire some locks. If not, adds item to queue

        :lock_ids set<string>: set of ids that this object needs to wait on
        :queue_obj object: whatever kind of object is being queued

        First checks the current locks, then makes sure this object would be the first in each
        queue it would sit in

        Returns :boolean: True if it acquired the lock, False if it was added to queue
        """
        queue_obj_id = self.get_queue_obj_id(queue_obj)
        if not lock_ids or self._set_lock(lock_ids):
            self.processing[queue_obj_id] = lock_ids
            return True
        queue_by_lock_id = self.queue_by_lock_id
        for lock_id in lock_ids:
            queue_by_lock_id[lock_id].append(queue_obj_id)
        self.objs_by_queue_id[queue_obj_id] = (queue_obj, lock_ids)
        return False

    def pop(self):
        """Pop a locked object and lock ids from the queue

        :returns: A tuple: `(<queue_obj>, <lock_ids>)`; `(None, None)`
        if nothing can acquire the lock currently.
        """
        def is_first(queue_id, lock_id):
            return queue_by_lock_id[lock_id][0] == queue_id

        seen = set()
        queue_by_lock_id = self.queue_by_lock_id
        objs_by_queue_id = self.objs_by_queue_id
        for queue in queue_by_lock_id.values():
            queue_id = queue[0]
            if queue_id in seen:
                continue
            lock_ids = objs_by_queue_id[queue_id][1]
            if all(is_first(queue_id, x) for x in lock_ids) and self._set_lock(lock_ids):
                return self._pop_queue_obj(queue_id)
            seen.add(queue_id)
        return None, None

    def _pop_queue_obj(self, queued_obj_id):
        """Removes and returns a queued obj from data model

        :queue_obj_id string: An id of an object of the type in the queues

        Assumes the obj is the first in every queue it inhabits.
        """
        queue_obj, lock_ids = self.objs_by_queue_id.pop(queued_obj_id)
        queue_by_lock_id = self.queue_by_lock_id
        for lock_id in lock_ids:
            queue = queue_by_lock_id[lock_id]
            assert queue[0] == queued_obj_id, (queue[0], queued_obj_id)
            if len(queue) == 1:
                queue_by_lock_id.pop(lock_id)
            else:
                queue.popleft()
        self.processing[queued_obj_id] = lock_ids
        return queue_obj, lock_ids

    def _is_any_locked(self, lock_ids):
        locked = self.currently_locked
        return any(lock_id in locked for lock_id in lock_ids)

    def _set_lock(self, lock_ids):
        """ Tries to set locks for given lock ids

        If already locked, returns false. If acquired, returns True
        """
        if self._is_any_locked(lock_ids):
            return False
        self.currently_locked.update(lock_ids)
        return True

    def release_lock(self, queue_obj):
        queue_obj_id = self.get_queue_obj_id(queue_obj)
        lock_ids = self.processing.pop(queue_obj_id)
        if lock_ids:
            self.currently_locked.difference_update(lock_ids)

    def __len__(self):
        """Return the number of objects in the queue"""
        return len(self.objs_by_queue_id)

    @property
    def full(self):
        if self.max_size == -1:
            return False
        return len(self) >= self.max_size


def _fix_replacement_form_problem_in_couch(doc):
    """Fix replacement form created by swap_duplicate_xforms

    The replacement form was incorrectly created with "problem" text,
    which causes it to be counted as an error form, and that messes up
    the diff counts at the end of this migration.

    NOTE the replacement form's _id does not match instanceID in its
    form.xml. That issue is not resolved here.

    See:
    - corehq/apps/cleanup/management/commands/swap_duplicate_xforms.py
    - couchforms/_design/views/all_submissions_by_domain/map.js
    """
    problem = doc["problem"]
    assert problem.startswith(PROBLEM_TEMPLATE_START), doc
    assert doc["doc_type"] == "XFormInstance", doc
    deprecated_id = problem[len(PROBLEM_TEMPLATE_START):].split(" on ", 1)[0]
    form = XFormInstance.wrap(doc)
    form.deprecated_form_id = deprecated_id
    form.history.append(XFormOperation(
        user="system",
        date=datetime.utcnow(),
        operation="Resolved bad duplicate form during couch-to-sql "
        "migration. Original problem: %s" % problem,
    ))
    form.problem = None
    old_form = XFormInstance.get(deprecated_id)
    if old_form.initial_processing_complete and not form.initial_processing_complete:
        form.initial_processing_complete = True
    form.save()
    return form.to_json()


def get_case_ids(form):
    """Get a set of case ids referenced in form

    Gracefully handles missing XML, but will omit case ids referenced in
    ledger updates if XML is missing.
    """
    try:
        return get_case_ids_from_form(form)
    except MissingFormXml:
        return {update.id for update in get_case_updates(form)}
