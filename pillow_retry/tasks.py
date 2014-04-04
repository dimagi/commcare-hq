from celery.task import task
import sys
from django.conf import settings
from dimagi.utils.couch.cache import cache_core
from pillow_retry.models import PillowError
from pillowtop.utils import import_pillow_string


@task
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
            return
        
        doc_id = error_doc.doc_id
        pillow_class = error_doc.pillow
        try:
            pillow = import_pillow_string(pillow_class)
            pillow.process_change({'id': doc_id}, is_retry_attempt=True)
        except:
            ex_type, ex_value, ex_tb = sys.exc_info()
            error_doc.add_attempt(ex_value, ex_tb)
            error_doc.save()
        else:
            error_doc.delete()
        finally:
            lock.release()





