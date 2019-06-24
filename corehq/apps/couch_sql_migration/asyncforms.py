from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta

import gevent
import six
from gevent.pool import Pool

from casexml.apps.case.xform import get_case_ids_from_form, get_case_updates

from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import (
    PROBLEM_TEMPLATE_START,
)
from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.form_processor.parsers.ledgers.form import MissingFormXml
from couchforms.models import XFormInstance, XFormOperation
from dimagi.utils.chunked import chunked

log = logging.getLogger(__name__)


class AsyncFormProcessor(object):

    def __init__(self, statedb, migrate_form):
        self.statedb = statedb
        self.migrate_form = migrate_form
        self.processed_docs = 0

    def __enter__(self):
        self.pool = Pool(15)
        self.queues = PartiallyLockingQueue()
        self._rebuild_queues(self.statedb.pop_saved_resume_state())
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        if exc_type is None:
            self._finish_processing_queues()
        self.statedb.save_resume_state(self.queues.queue_ids)
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
            if six.text_type(doc['problem']).startswith(PROBLEM_TEMPLATE_START):
                doc = _fix_replacement_form_problem_in_couch(doc)
            else:
                self.statedb.add_problem_form(form_id)
                return
        try:
            wrapped_form = XFormInstance.wrap(doc)
        except Exception:
            log.exception("Error migrating form %s", form_id)
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
            self.queues.release_lock_for_queue_obj(wrapped_form)

    def _try_to_empty_queues(self):
        while True:
            new_wrapped_form, case_ids = self.queues.get_next()
            if not new_wrapped_form:
                break
            self.pool.spawn(self._async_migrate_form, new_wrapped_form, case_ids)

    def _finish_processing_queues(self):
        update_interval = timedelta(seconds=10)
        next_check = datetime.now()
        pool = self.pool
        while self.queues.has_next():
            wrapped_form, case_ids = self.queues.get_next()
            if wrapped_form:
                pool.spawn(self._async_migrate_form, wrapped_form, case_ids)
            else:
                gevent.sleep()  # swap greenlets

            now = datetime.now()
            if now > next_check:
                remaining_items = self.queues.remaining_items + len(pool)
                log.info('Waiting on {} docs'.format(remaining_items))
                next_check += update_interval

        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))

        unprocessed = self.queues.queue_ids
        if unprocessed:
            log.error("Unprocessed forms (unexpected): %s", unprocessed)


class PartiallyLockingQueue(object):
    """ Data structure that holds a queue of objects returning them as locks become free

    This is not currently thread safe

    Interface:
    `.try_obj(lock_ids, queue_obj)` use to add a new object, seeing if it can be
        processed immediately
    `.get_next()` use to get the next object that can be processed
    `.has_next()` use to make sure there are still objects in the queue
    `.release_lock_for_queue_obj(queue_obj)` use to release the locks associated
        with an object once finished processing
    """

    def __init__(self, queue_id_param="form_id", max_size=10000):
        """
        :queue_id_param string: param of the queued objects to pull an id from
        :max_size int: the maximum size the queue should reach. -1 means no limit
        """
        self.queue_by_lock_id = defaultdict(deque)
        self.lock_ids_by_queue_id = {}
        self.queue_objs_by_queue_id = {}
        self.currently_locked = set()
        self.max_size = max_size

        def get_queue_obj_id(queue_obj):
            return getattr(queue_obj, queue_id_param)
        self.get_queue_obj_id = get_queue_obj_id

    @property
    def queue_ids(self):
        """Return a list of queue object ids

        Queue state can be ruilt using this list by looking up each
        queue object and lock ids and passing them to `try_obj()`.
        """
        return list(self.lock_ids_by_queue_id)

    def try_obj(self, lock_ids, queue_obj):
        """ Checks if the object can acquire some locks. If not, adds item to queue

        :lock_ids set<string>: set of ids that this object needs to wait on
        :queue_obj object: whatever kind of object is being queued

        First checks the current locks, then makes sure this object would be the first in each
        queue it would sit in

        Returns :boolean: True if it acquired the lock, False if it was added to queue
        """
        if not lock_ids:
            self._add_item(lock_ids, queue_obj, to_queue=False)
            return True
        if self._check_lock(lock_ids):  # if it's currently locked, it can't acquire the lock
            self._add_item(lock_ids, queue_obj)
            return False
        for lock_id in lock_ids:  # if other objs are waiting for the same locks, it has to wait
            queue = self.queue_by_lock_id[lock_id]
            if queue:
                self._add_item(lock_ids, queue_obj)
                return False
        self._add_item(lock_ids, queue_obj, to_queue=False)
        self._set_lock(lock_ids)
        return True

    def get_next(self):
        """Returns the next object and lock ids that can be processed

        Iterates through the first object in each queue, then checks
        that that object is the first in every lock queue it is in.

        :returns: A tuple: `(<queue_obj>, <lock_ids>)`; `(None, None)`
        if nothing can acquire the lock currently.
        """
        def is_first(queue_id, lock_id):
            return queue_by_lock_id[lock_id][0] == queue_id

        queue_by_lock_id = self.queue_by_lock_id
        lock_ids_by_queue_id = self.lock_ids_by_queue_id
        for queue in six.itervalues(queue_by_lock_id):
            if not queue:
                continue
            queue_id = queue[0]
            lock_ids = lock_ids_by_queue_id[queue_id]
            if all(is_first(queue_id, x) for x in lock_ids) and self._set_lock(lock_ids):
                return self._pop_queue_obj(queue_id), lock_ids
        return None, None

    def has_next(self):
        """ Makes sure there are still objects in the queue

        Returns :boolean: True if there are objs left, False if not
        """
        for queue in six.itervalues(self.queue_by_lock_id):
            if queue:
                return True
        return False

    def release_lock_for_queue_obj(self, queue_obj):
        """ Releases all locks for an object in the queue

        :queue_obj obj: An object of the type in the queues

        At some point in the future it might raise an exception if it trys
        releasing a lock that isn't held
        """
        queue_obj_id = self.get_queue_obj_id(queue_obj)
        lock_ids = self.lock_ids_by_queue_id.pop(queue_obj_id, None)
        if lock_ids:
            self._release_lock(lock_ids)
            return True
        return False

    @property
    def remaining_items(self):
        return len(self.queue_objs_by_queue_id)

    @property
    def full(self):
        if self.max_size == -1:
            return False
        return self.remaining_items >= self.max_size

    def _add_item(self, lock_ids, queue_obj, to_queue=True):
        """
        :to_queue boolean: adds object to queues if True, just to lock tracking if not
        """
        queue_obj_id = self.get_queue_obj_id(queue_obj)
        if to_queue:
            for lock_id in lock_ids:
                self.queue_by_lock_id[lock_id].append(queue_obj_id)
            self.queue_objs_by_queue_id[queue_obj_id] = queue_obj
        self.lock_ids_by_queue_id[queue_obj_id] = lock_ids

    def _pop_queue_obj(self, queued_obj_id):
        """Removes and returns a queued obj from data model

        :queue_obj_id string: An id of an object of the type in the queues

        Assumes the obj is the first in every queue it inhabits. This seems reasonable
        for the intended use case, as this function should only be used by `.get_next`.

        Raises UnexpectedObjectException if this assumption doesn't hold
        """
        lock_ids = self.lock_ids_by_queue_id.get(queued_obj_id)
        for lock_id in lock_ids:
            queue = self.queue_by_lock_id[lock_id]
            if queue[0] != queued_obj_id:
                raise UnexpectedObjectException("This object shouldn't be removed")
        for lock_id in lock_ids:
            queue = self.queue_by_lock_id[lock_id]
            queue.popleft()
        return self.queue_objs_by_queue_id.pop(queued_obj_id)

    def _check_lock(self, lock_ids):
        return any(lock_id in self.currently_locked for lock_id in lock_ids)

    def _set_lock(self, lock_ids):
        """ Trys to set locks for given lock ids

        If already locked, returns false. If acquired, returns True
        """
        if self._check_lock(lock_ids):
            return False
        self.currently_locked.update(lock_ids)
        return True

    def _release_lock(self, lock_ids):
        self.currently_locked.difference_update(lock_ids)


class UnexpectedObjectException(Exception):
    pass


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
    """Get case ids referenced in form

    Gracefully handles missing XML, but will omit case ids referenced in
    ledger updates if XML is missing.
    """
    try:
        return get_case_ids_from_form(form)
    except MissingFormXml:
        return [update.id for update in get_case_updates(form)]
