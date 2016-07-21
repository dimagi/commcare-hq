import math
import time
import traceback
from datetime import datetime
from functools import wraps

from couchdbkit.exceptions import ResourceNotFound
from django import db
from django.db.utils import InterfaceError as DjangoInterfaceError
from elasticsearch.exceptions import RequestError, ConnectionError, NotFoundError, ConflictError
from psycopg2._psycopg import InterfaceError as Psycopg2InterfaceError

from dimagi.utils.couch import LockManager
from dimagi.utils.decorators.memoized import memoized
from pillowtop.checkpoints.manager import PillowCheckpoint, get_default_django_checkpoint_for_legacy_pillow_class
from pillowtop.checkpoints.util import get_machine_id, construct_checkpoint_doc_id_from_name
from pillowtop.const import CHECKPOINT_FREQUENCY
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.es_utils import completely_initialize_pillow_index, doc_exists
from pillowtop.feed.couch import CouchChangeFeed
from pillowtop.logger import pillow_logging
from pillowtop.pillow.interface import PillowBase
from pillowtop.utils import prepare_bulk_payloads

try:
    from corehq.util.soft_assert import soft_assert
    _assert = soft_assert(to='@'.join(['czue', 'dimagi.com']), fail_if_debug=True)
except ImportError:
    # hack for dependency resolution if corehq not available
    _assert = lambda assertion, message: None


WAIT_HEARTBEAT = 10000
CHANGES_TIMEOUT = 60000
RETRY_INTERVAL = 2  # seconds, exponentially increasing
MAX_RETRIES = 4  # exponential factor threshold for alerts


class PillowtopIndexingError(Exception):
    pass


class PillowtopNetworkError(Exception):
    pass


def ms_from_timedelta(td):
    """
    Given a timedelta object, returns a float representing milliseconds
    """
    return (td.seconds * 1000) + (td.microseconds / 1000.0)


def lock_manager(obj):
    if isinstance(obj, LockManager):
        return obj
    else:
        return LockManager(obj, None)


class BasicPillow(PillowBase):
    """
    BasicPillow is actually a CouchPillow. PillowBase defines the actual interface.
    """
    checkpoint_frequency = CHECKPOINT_FREQUENCY
    couch_filter = None  # string for filter if needed
    extra_args = {}  # filter args if needed
    document_class = None  # couchdbkit Document class
    _couch_db = None
    include_docs = True
    use_locking = False

    def __init__(self, couch_db=None, document_class=None, checkpoint=None, change_feed=None):
        if document_class:
            self.document_class = document_class

        self._couch_db = couch_db
        self._checkpoint = checkpoint
        self._change_feed = change_feed

        if self.use_locking:
            # document_class must be a CouchDocLockableMixIn
            assert hasattr(self.document_class, 'get_obj_lock_by_id')

    @property
    def pillow_id(self):
        # for legacy reasons, by default a Pillow's ID is just it's class name
        return self.__class__.__name__

    def get_couch_db(self):
        if self._couch_db is None:
            self._couch_db = self.get_default_couch_db()
        return self._couch_db

    def set_couch_db(self, couch_db):
        self._couch_db = couch_db

    def get_default_couch_db(self):
        return self.document_class.get_db() if self.document_class else None

    @property
    def couch_db(self):
        _assert(False, 'People should not be using the couch_db properties!')
        return self.get_couch_db()

    @couch_db.setter
    def couch_db(self, value):
        _assert(False, 'People should not be using the couch_db properties!')
        self._couch_db = value

    @property
    def document_store(self):
        return CouchDocumentStore(self.get_couch_db())

    @property
    def checkpoint(self):
        if self._checkpoint is None:
            self._checkpoint = self._get_default_checkpoint()
        return self._checkpoint

    def _get_default_checkpoint(self):
        return PillowCheckpoint(
            construct_checkpoint_doc_id_from_name(self.get_name()),
        )

    def get_change_feed(self):
        if self._change_feed is None:
            self._change_feed = self._get_default_change_feed()
        return self._change_feed

    def _get_default_change_feed(self):
        return CouchChangeFeed(
            couch_db=self.get_couch_db(),
            include_docs=self.include_docs,
            couch_filter=self.couch_filter,
            extra_couch_view_params=self.extra_args
        )

    @memoized
    def get_name(self):
        return self.get_legacy_name()

    @classmethod
    def get_legacy_name(cls):
        return "%s.%s.%s" % (cls._get_base_name(), cls.__name__, get_machine_id())

    @classmethod
    def _get_base_name(cls):
        return cls.__module__

    def process_change(self, change):
        """
        Parent processsor for a pillow class - this should not be overridden.
        This workflow is made for the situation where 1 change yields 1 transport/transaction
        """
        with lock_manager(self.change_trigger(change)) as t:
            if t is not None:
                tr = self.change_transform(t)
                if tr is not None:
                    self.change_transport(tr)

    def fire_change_processed_event(self, change, context):
        if context.changes_seen % self.checkpoint_frequency == 0 and context.do_set_checkpoint:
            self.set_checkpoint(change)

    def change_trigger(self, changes_dict):
        """
        Step one of pillowtop process
        For a given _changes indicator, the changes dict (the id, _rev) is sent here.

        Note, a couch _changes line is: {'changes': [], 'id': 'guid',  'seq': <int>}
        a 'deleted': True might be there too

        whereas a doc_dict is _id
        Should return a doc_dict
        """
        if changes_dict.get('deleted', False):
            # override deleted behavior on consumers that deal with deletions
            return None
        id = changes_dict['id']
        if self.use_locking:
            lock = self.document_class.get_obj_lock_by_id(id)
            lock.acquire()
            return LockManager(self.get_couch_db().open_doc(id), lock)
        elif changes_dict.get('doc', None) is not None:
            return changes_dict['doc']
        elif hasattr(changes_dict, 'get_document') and changes_dict.get_document():
            return changes_dict.get_document()
        else:
            # todo: remove this in favor of always using get_document() above
            try:
                return self.get_couch_db().open_doc(id)
            except ResourceNotFound:
                # doc was likely hard-deleted. treat like a deletion
                return None

    def change_transform(self, doc_dict):
        """
        Step two of the pillowtop processor:
        Process/transform doc_dict if needed - by default, return the doc_dict passed.
        """
        return doc_dict

    def change_transport(self, doc_dict):
        """
        Step three of the pillowtop processor:
        Finish transport of doc if needed. Your subclass should implement this
        """
        raise NotImplementedError(
            "Error, this pillowtop subclass has not been configured to do anything!")


def send_to_elasticsearch(index, doc_type, doc_id, es_getter, name, data=None, retries=MAX_RETRIES,
        except_on_failure=False, update=False, delete=False):
    """
    More fault tolerant es.put method
    """
    data = data if data is not None else {}
    current_tries = 0
    while current_tries < retries:
        try:
            if delete:
                es_getter().delete(index, doc_type, doc_id)
            elif update:
                params = {'retry_on_conflict': 2}
                es_getter().update(index, doc_type, doc_id, body={"doc": data}, params=params)
            else:
                es_getter().create(index, doc_type, body=data, id=doc_id)
            break
        except ConnectionError, ex:
            current_tries += 1
            pillow_logging.error("[%s] put_robust error %s attempt %d/%d" % (
                name, ex, current_tries, retries))

            if current_tries == retries:
                message = "[%s] Max retry error on %s/%s/%s" % (name, index, doc_type, doc_id)
                if except_on_failure:
                    raise PillowtopIndexingError(message)
                else:
                    pillow_logging.error(message)

            time.sleep(math.pow(RETRY_INTERVAL, current_tries))
        except RequestError as ex:
            error_message = "Pillowtop put_robust error [%s]:\n%s\n\tpath: %s/%s/%s\n\t%s" % (
                name,
                ex.error or "No error message",
                index, doc_type, doc_id,
                data.keys())

            if except_on_failure:
                raise PillowtopIndexingError(error_message)
            else:
                pillow_logging.error(error_message)
            break
        except ConflictError:
            break  # ignore the error if a doc already exists when trying to create it in the index
        except NotFoundError:
            break


def retry_on_connection_failure(fn):
    @wraps(fn)
    def _inner(*args, **kwargs):
        retry = kwargs.pop('retry', True)
        try:
            return fn(*args, **kwargs)
        except db.utils.DatabaseError:
            # we have to do this manually to avoid issues with
            # open transactions and already closed connections
            db.transaction.rollback()
            # re raise the exception for additional error handling
            raise
        except (Psycopg2InterfaceError, DjangoInterfaceError):
            # force closing the connection to prevent Django from trying to reuse it.
            # http://www.tryolabs.com/Blog/2014/02/12/long-time-running-process-and-django-orm/
            db.connection.close()
            if retry:
                _inner(retry=False, *args, **kwargs)
            else:
                # re raise the exception for additional error handling
                raise

    return _inner
