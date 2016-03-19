from celery.task import task
import sys
from couchdbkit.exceptions import ResourceNotFound
from django.conf import settings
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch import release_lock
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.logging import notify_error
from pillow_retry.models import PillowError
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_pillow_by_name, get_pillow_instance
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@task(queue='pillow_retry_queue', ignore_result=True)
def process_pillow_retry(error_doc_id):
    # Redis error logged in get_redis_client
    try:
        client = cache_core.get_redis_client()
    except cache_core.RedisClientError:
        return

    # Prevent more than one task from processing this error, just in case
    # it got enqueued twice.
    lock = client.lock(
        "pillow-retry-processing-%s" % error_doc_id,
        timeout=settings.PILLOW_RETRY_PROCESSING_LOCK_TIMEOUT*60
    )
    if lock.acquire(blocking=False):
        try:
            error_doc = PillowError.objects.get(id=error_doc_id)
        except PillowError.DoesNotExist:
            release_lock(lock, True)
            return

        pillow_name_or_class = error_doc.pillow
        try:
            pillow = get_pillow_by_name(pillow_name_or_class)
        except PillowNotFoundError:
            if not settings.UNIT_TESTING:
                _assert = soft_assert(to='@'.join(['czue', 'dimagi.com']))
                _assert(False, 'Pillow retry {} is still using legacy class {}'.format(
                    error_doc.pk, pillow_name_or_class
                ))
            pillow = _try_legacy_import(pillow_name_or_class)

        if not pillow:
            notify_error((
                "Could not find pillowtop class '%s' while attempting a retry. "
                "If this pillow was recently deleted then this will be automatically cleaned up eventually. "
                "If not, then this should be looked into."
            ) % pillow_name_or_class)
            try:
                error_doc.total_attempts = PillowError.multi_attempts_cutoff() + 1
                error_doc.save()
            finally:
                release_lock(lock, True)
                return


        change = error_doc.change_object
        if pillow.include_docs:
            try:
                change.set_document(pillow.get_couch_db().open_doc(change.id))
            except ResourceNotFound:
                change.deleted = True

        try:
            try:
                from corehq.apps.userreports.pillow import ConfigurableReportKafkaPillow
                if isinstance(pillow, ConfigurableReportKafkaPillow):
                    raise Exception('this is temporarily not supported!')
            except ImportError:
                pass
            pillow.process_change(change, is_retry_attempt=True)
        except Exception:
            ex_type, ex_value, ex_tb = sys.exc_info()
            error_doc.add_attempt(ex_value, ex_tb)
            error_doc.queued = False
            error_doc.save()
        else:
            error_doc.delete()
        finally:
            release_lock(lock, True)


def _try_legacy_import(pillow_name_or_class):
    try:
        return get_pillow_instance(pillow_name_or_class)
    except ValueError:
        # all fluff pillows have module path of 'fluff' so can't be imported directly
        if '.' in pillow_name_or_class:
            _, pillow_name_or_class = pillow_name_or_class.rsplit('.', 1)
        try:
            return get_pillow_by_name(pillow_name_or_class)
        except PillowNotFoundError:
            return None
