from celery.task import task
from dimagi.utils.couch.cache.cache_core import get_redis_client
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation



class CouldNotAqcuireLock(Exception):
    pass


@task(bind=True, queue='background_queue', ignore_result=True,
      default_retry_delay=10, max_retries=3)
def sync_administrative_status(self, location_type):
    client = get_redis_client()
    key = "{location_type.domain}-{location_type.pk}".format(location_type=location_type)
    lock = client.lock(key, timeout=10)
    if lock.acquire(blocking=False):
        try:
            # Actually call the function
            for location in SQLLocation.objects.filter(location_type=location_type):
                # Saving the location should be sufficient for it to pick up the
                # new supply point.  We'll need to save it anyways to store the new
                # supply_point_id.
                location.save()
            if location_type.administrative:
                _hide_stock_states(location_type)
            else:
                _unhide_stock_states(location_type)
        except Exception:
            # Don't leave the lock around if the task fails
            lock.release()
            raise
        lock.release()
    else:
        msg = "Could not aquire lock '{}' for task '{}'.".format(
            key, 'sync_administrative_status')
        self.retry(exc=CouldNotAqcuireLock(msg))


def _hide_stock_states(location_type):
    (StockState.objects
     .filter(sql_location__location_type=location_type)
     .update(sql_location=None))


def _unhide_stock_states(location_type):
    for location in SQLLocation.objects.filter(location_type=location_type):
        (StockState.objects
         .filter(case_id=location.supply_point_id)
         .update(sql_location=location))
