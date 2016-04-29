from functools import wraps
import logging
from couchdbkit.exceptions import ResourceNotFound
from elasticsearch.exceptions import RequestError, ConnectionError, NotFoundError, ConflictError
from psycopg2._psycopg import InterfaceError as Psycopg2InterfaceError
from django.db.utils import InterfaceError as DjangoInterfaceError
from datetime import datetime, timedelta
import hashlib
import traceback
import math
import time

import simplejson
import sys

from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.couch import LockManager
from pillow_retry.models import PillowError
from pillowtop.checkpoints.manager import PillowCheckpoint, get_default_django_checkpoint_for_legacy_pillow_class
from pillowtop.checkpoints.util import get_machine_id, construct_checkpoint_doc_id_from_name
from pillowtop.const import CHECKPOINT_FREQUENCY
from pillowtop.couchdb import CachedCouchDB

from django import db
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

    def processor(self, change, context):
        """
        Parent processsor for a pillow class - this should not be overridden.
        This workflow is made for the situation where 1 change yields 1 transport/transaction
        """
        self.process_change(change)

    def fire_change_processed_event(self, change, context):
        if context.changes_seen % self.checkpoint_frequency == 0 and context.do_set_checkpoint:
            self.set_checkpoint(change)

    def process_change(self, change, is_retry_attempt=False):
        try:
            with lock_manager(self.change_trigger(change)) as t:
                if t is not None:
                    tr = self.change_transform(t)
                    if tr is not None:
                        self.change_transport(tr)
        except Exception, ex:
            if not is_retry_attempt:
                self._handle_pillow_error(change, ex)
            else:
                raise

    def _handle_pillow_error(self, change, exception):
        try:
            # This breaks the module boundary by using a show function defined in commcare-hq
            # but it was decided that it wasn't worth the effort to maintain the separation.
            meta = self.get_couch_db().show('domain_shows/domain_date', change['id'])
        except ResourceNotFound:
            # Show function does not exist
            meta = None
        error = PillowError.get_or_create(change, self, change_meta=meta)
        error.add_attempt(exception, sys.exc_info()[2])
        error.save()
        pillow_logging.exception(
            "[%s] Error on change: %s, %s. Logged as: %s" % (
                self.get_name(),
                change['id'],
                exception,
                error.id
            )
        )

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
            return self.get_couch_db().open_doc(id)

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


PYTHONPILLOW_CHUNK_SIZE = 250
PYTHONPILLOW_CHECKPOINT_FREQUENCY = CHECKPOINT_FREQUENCY * 10
PYTHONPILLOW_MAX_WAIT_TIME = 60


class PythonPillow(BasicPillow):
    """
    A pillow that does filtering in python instead of couch.

    Useful because it will actually set checkpoints throughout even if there
    are no matched docs.

    In initial profiling this was also 2-3x faster than the couch-filtered
    version.

    Subclasses should override the python_filter function to perform python
    filtering.
    """
    process_deletions = False

    def __init__(self, document_class=None, chunk_size=PYTHONPILLOW_CHUNK_SIZE,
                 checkpoint_frequency=PYTHONPILLOW_CHECKPOINT_FREQUENCY,
                 couch_db=None, checkpoint=None, change_feed=None, preload_docs=True):
        """
        Use chunk_size = 0 to disable chunking
        """
        super(PythonPillow, self).__init__(
            document_class=document_class,
            checkpoint=checkpoint,
            couch_db=couch_db,
            change_feed=change_feed,
        )
        self.change_queue = []
        self.chunk_size = chunk_size
        self.use_chunking = chunk_size > 0
        self.checkpoint_frequency = checkpoint_frequency
        self.include_docs = not self.use_chunking
        self.last_processed_time = None
        self.preload_docs = preload_docs

    def get_default_couch_db(self):
        if self.document_class and self.use_chunking:
            return CachedCouchDB(self.document_class.get_db().uri, readonly=False)
        else:
            return super(PythonPillow, self).get_default_couch_db()

    def python_filter(self, change):
        """
        Should return True if the doc is to be processed by your pillow
        """
        return True

    def process_chunk(self):
        def _assert_change_has_id(change):
            if 'id' not in change:
                _assert(False, "expected 'id' in change, but wasn't found! change is: {}".format(
                    simplejson.dumps(change)
                ))
                return False
            return True

        changes_to_process = filter(_assert_change_has_id, self.change_queue)
        if self.preload_docs:
            self.get_couch_db().bulk_load([change['id'] for change in changes_to_process],
                                     purge_existing=True)
        for change in changes_to_process:
            if self.preload_docs:
                doc = self.get_couch_db().open_doc(change['id'], check_main=False)
                change.set_document(doc)

            # a valid change is either a non-preload situation or a valid doc + a filter match
            valid_change = (not self.preload_docs or change.document) and self.python_filter(change)
            valid_deletion = self.process_deletions and change.get('deleted', None)
            if valid_change or valid_deletion:
                try:
                    self.process_change(change)
                except Exception:
                    logging.exception('something went wrong processing change %s (%s)' %
                                      (change.get('seq', None), change['id']))

        # reset the queue after we've processed this chunk
        self.change_queue = []
        self.last_processed_time = datetime.utcnow()

    @property
    def queue_full(self):
        return len(self.change_queue) > self.chunk_size

    @property
    def wait_expired(self):
        if not self.last_processed_time:
            return False

        wait_time = datetime.utcnow() - self.last_processed_time
        return wait_time > timedelta(seconds=PYTHONPILLOW_MAX_WAIT_TIME)

    def processor(self, change, context):
        if self.use_chunking:
            self.change_queue.append(change)
            if self.queue_full or self.wait_expired:
                self.process_chunk()
        elif self.python_filter(change) or (change.get('deleted', None) and self.process_deletions):
            self.process_change(change)

    def fire_change_processed_event(self, change, context):
        if context.changes_seen % self.checkpoint_frequency == 0 and context.do_set_checkpoint:
            # if using chunking make sure we never allow the checkpoint to get in
            # front of the chunks
            if self.use_chunking:
                self.process_chunk()
            self.set_checkpoint(change)

    def run(self):
        self.change_queue = []
        self.last_processed_time = datetime.utcnow()
        super(PythonPillow, self).run()


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


class AliasedElasticPillow(BasicPillow):
    """
    This pillow class defines it as being alias-able. That is, when you query it, you use an
    Alias to access it.

    This could be for varying reasons -  to make an index by certain metadata into its own index
    for performance/separation reasons

    Or, for our initial use case, needing to version/update the index mappings on the fly with
    minimal disruption.


    The workflow for altering an AliasedElasticPillow is that if you know you made a change, the
    pillow will create a new Index with a new md5sum as its suffix. Once it's finished indexing,
    you will need to flip the alias over to it.
    """
    es_index = ""
    es_type = ""
    es_alias = ''
    es_meta = {}
    es_timeout = 3  # in seconds
    default_mapping = None  # the default elasticsearch mapping to use for this
    bulk = False

    # Note - we allow for for existence because we do not care - we want the ES
    # index to always have the latest version of the case based upon ALL changes done to it.
    allow_updates = True

    def __init__(self, online=True, **kwargs):
        """
        online determines whether the ES index should initialize itself on pillow creation
        """
        if 'checkpoint' not in kwargs:
            kwargs['checkpoint'] = get_default_django_checkpoint_for_legacy_pillow_class(self.__class__)
        super(AliasedElasticPillow, self).__init__(**kwargs)
        # online=False is used in unit tests
        if online:
            completely_initialize_pillow_index(self)

    def get_doc_path(self, doc_id):
        return "%s/%s/%s" % (self.es_index, self.es_type, doc_id)

    @memoized
    def get_es_new(self):
        from corehq.elastic import get_es_new
        return get_es_new(timeout=self.es_timeout)

    def change_trigger(self, changes_dict):
        id = changes_dict['id']
        if changes_dict.get('deleted', False):
            try:
                if doc_exists(self, id):
                    self.get_es_new().delete(self.es_index, self.es_type, id)
            except Exception, ex:
                pillow_logging.error(
                    "ElasticPillow: error deleting route %s - ignoring: %s" % (
                        self.get_doc_path(changes_dict['id']),
                        ex,
                    )
                )
            return None
        return super(AliasedElasticPillow, self).change_trigger(changes_dict)

    def send_robust(self, doc_dict, retries=MAX_RETRIES, except_on_failure=False, update=False):
        send_to_elasticsearch(
            index=self.es_index,
            doc_type=self.es_type,
            doc_id=doc_dict['_id'],
            es_getter=self.get_es_new,
            name=self.get_name(),
            data=doc_dict,
            retries=retries,
            except_on_failure=except_on_failure,
            update=update,
        )

    def change_transport(self, doc_dict):
        """
        Save the document to ElasticSearch
        """
        try:
            if not self.bulk:
                doc_exists_val = doc_exists(self, doc_dict)

                if self.allow_updates:
                    can_put = True
                else:
                    can_put = not doc_exists_val

                if can_put and not self.bulk:
                    self.send_robust(doc_dict, update=doc_exists_val)
        except Exception, ex:
            tb = traceback.format_exc()
            pillow_logging.error(
                "PillowTop [%(pillow_name)s]: Aliased Elastic Pillow transport change data doc_id: %(doc_id)s to elasticsearch error: %(error)s\ntraceback: %(tb)s\n" %
                {
                    "pillow_name": self.get_name(),
                    "doc_id": doc_dict['_id'],
                    "error": ex,
                    "tb": tb
                }
            )
            raise

    def process_bulk(self, changes):
        if not changes:
            return
        self.allow_updates = False
        self.bulk = True
        bstart = datetime.utcnow()
        bulk_changes = self.bulk_builder(changes)

        max_payload_size = pow(10, 8)  # ~ 100Mb
        payloads = prepare_bulk_payloads(bulk_changes, max_payload_size)
        if len(payloads) > 1:
            pillow_logging.info("%s,payload split into %s parts" % (self.get_name(), len(payloads)))

        pillow_logging.info(
            "%s,prepare_bulk,%s" % (self.get_name(), str(ms_from_timedelta(datetime.utcnow() - bstart) / 1000.0)))
        send_start = datetime.utcnow()
        for payload in payloads:
            self.send_bulk(payload)
        pillow_logging.info(
            "%s,send_bulk,%s" % (self.get_name(), str(ms_from_timedelta(datetime.utcnow() - send_start) / 1000.0)))

    def send_bulk(self, payload):
        self.get_es_new().bulk(payload)

    @staticmethod
    def calc_mapping_hash(mapping):
        return hashlib.md5(simplejson.dumps(mapping, sort_keys=True)).hexdigest()

    @classmethod
    def get_unique_id(cls):
        """
        a unique identifier for the pillow - typically the hash associated with the index
        """
        # for legacy reasons this is the default until we remove it.
        return cls.calc_meta()

    @classmethod
    def calc_meta(cls):
        # todo: we should get rid of this and have subclasses override get_unique_id
        # instead of calc_meta
        raise NotImplementedError("Need to either override get_unique_id or implement your own meta calculator")

    def bulk_builder(self, changes):
        """
        http://www.elasticsearch.org/guide/reference/api/bulk.html
        bulk loader follows the following:
        { "index" : { "_index" : "test", "_type" : "type1", "_id" : "1" } }\n
        { "field1" : "value1" }\n
        """
        for change in changes:
            try:
                with lock_manager(self.change_trigger(change)) as t:
                    if t is not None:
                        tr = self.change_transform(t)
                        if tr is not None:
                            self.change_transport(tr)
                            yield {
                                "index": {
                                    "_index": self.es_index,
                                    "_type": self.es_type,
                                    "_id": tr['_id']
                                }
                            }
                            yield tr
            except Exception, ex:
                pillow_logging.error(
                    "Error on change: %s, %s" % (change['id'], ex)
                )

    @memoized
    def get_name(self):
        """
        Gets the doc_name in which to set the checkpoint for itself, based upon
        class name and the hashed name representation.
        """
        return self.get_legacy_name()

    @classmethod
    def get_legacy_name(cls):
        return "%s.%s.%s.%s" % (
            cls.__module__, cls.__name__, cls.get_unique_id(), get_machine_id())


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


class SQLPillowMixIn(object):

    def change_trigger(self, changes_dict):
        if changes_dict.get('deleted', False):
            self.change_transport({'_id': changes_dict['id']}, delete=True)
            return None
        return super(SQLPillowMixIn, self).change_trigger(changes_dict)

    @retry_on_connection_failure
    @db.transaction.atomic
    def change_transport(self, doc_dict, delete=False):
        self.process_sql(doc_dict, delete)

    def process_sql(self, doc_dict, delete=False):
        pass


class SQLPillow(SQLPillowMixIn, BasicPillow):

    def __init__(self):
        checkpoint = get_default_django_checkpoint_for_legacy_pillow_class(self.__class__)
        super(SQLPillow, self).__init__(checkpoint=checkpoint)
