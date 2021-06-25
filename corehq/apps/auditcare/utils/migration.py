from corehq.apps.auditcare.models import AuditcareMigrationMeta
from django.core.cache import cache
import gevent
from dimagi.utils.dates import force_to_datetime


class AuditCareMigrationUtil():

    def __init__(self):
        self.start_key = "auditcare_migration_2021_next_batch_time"
        self.start_lock_key = f"{self.start_key}_lock"

    def get_next_batch_start(self, counter=0):
        if self.is_start_key_lock_acquired():
            gevent.sleep(1)
            if counter >= 10:
                raise Exception("Unable to get next batch start time")
            return self.get_next_batch_start(counter=counter + 1)
        return cache.get(self.start_key)

    def generate_batches(self, worker_count, batch_by):
        batches = []
        with cache.lock(self.start_lock_key, timeout=10):
            start_datetime = self.get_next_batch_start()
            if not start_datetime:
                # for the first call
                start_datetime = INITIAL_START_DATE

            start_time = _get_formatted_start_time(start_datetime, batch_by)
            end_time = None

            for index in range(worker_count):
                end_time = _get_end_time(start_time, batch_by)
                batches.append([start_time, end_time])
                start_time = end_time
            self.set_next_batch_start(end_time)
            if end_time > datetime.now():
                print("Migration successfully done")
                exit(1)
        return batches

    def set_next_batch_start(self, value):
        cache.set(self.start_key, value)

    def acquire_read_lock(self):
        cache.set(self.start_lock_key, 1)

    def release_read_lock(self):
        cache.delete(self.start_lock_key)

    def is_start_key_lock_acquired(self):
        return cache.get(self.start_lock_key)

    def get_errored_keys(self, limit):
        errored_keys = (AuditcareMigrationMeta.objects
            .filter(state=AuditcareMigrationMeta.ERRORED)
            .values_list('key', flat=True)[:limit])

        return [get_datetimes_from_key(key) for key in errored_keys]

    def log_batch_start(self, key):
        if AuditcareMigrationMeta.objects.filter(key=key):
            return
        AuditcareMigrationMeta.objects.create(key=key, state=AuditcareMigrationMeta.STARTED)

    def set_batch_as_finished(self, key, count):
        AuditcareMigrationMeta.objects.filter(key=key).update(
            state=AuditcareMigrationMeta.FINISHED,
            record_count=count
        )

    def set_batch_as_errored(self, key):
        AuditcareMigrationMeta.objects.filter(key=key).update(state=AuditcareMigrationMeta.ERRORED)


def get_formatted_datetime_string(datetime_obj):
    return datetime_obj.strftime("%Y-%m-%d %H:%M:%S")


def get_datetimes_from_key(key):
    start, end = key.split("_")
    return [force_to_datetime(start), force_to_datetime(end)]


def _get_end_time(start_time, batch_by):
    delta = timedelta(hours=1) if batch_by == 'h' else timedelta(days=1)
    return start_time + delta


def _get_formatted_start_time(start_time, batch_by):
    if batch_by == 'h':
        return start_time.replace(minute=0, second=0, microsecond=0)
    else:
        return start_time.replace(hour=0, minute=0, second=0, microsecond=0)
