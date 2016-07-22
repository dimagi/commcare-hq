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
