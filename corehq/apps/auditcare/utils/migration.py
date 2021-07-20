from datetime import datetime, timedelta

from django.core.cache import cache

from dimagi.utils.dates import force_to_datetime

from corehq.apps.auditcare.models import AuditcareMigrationMeta
from corehq.apps.auditcare.utils.export import get_sql_start_date

CUTOFF_TIME = datetime(2013, 1, 1)
CACHE_TTL = 14 * 24 * 60 * 60  # 14 days


class AuditCareMigrationUtil():

    def __init__(self):
        self.start_key = "auditcare_migration_2021_next_batch_time"
        self.start_lock_key = "auditcare_migration_batch_lock"

    def get_next_batch_start(self):
        return cache.get(self.start_key)

    def generate_batches(self, worker_count, batch_by):
        batches = []
        # todo : Change get_fixed_start_date_for_sql to something generic
        cutoff_time = get_fixed_start_date_for_sql()
        if not cutoff_time:
            cutoff_time = datetime.now()
        with cache.lock(self.start_lock_key, timeout=10):
            start_datetime = self.get_next_batch_start()
            if not start_datetime:
                # for the first call
                if AuditcareMigrationMeta.objects.count() != 0:
                    raise Exception("Unable to get start time. Exiting.")
                start_datetime = INITIAL_START_DATE

            if start_datetime > cutoff_time:
                print("Migration Successfull")
                return

            start_time = _get_formatted_start_time(start_datetime, batch_by)
            end_time = None

            for index in range(worker_count):
                end_time = _get_end_time(start_time, batch_by)
                batches.append([start_time, end_time])
                if end_time > cutoff_time:
                    break
                start_time = end_time
            self.set_next_batch_start(end_time)

        return batches

    def set_next_batch_start(self, value):
        cache.set(self.start_key, value, CACHE_TTL)

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
    end_time = start_time - delta
    if batch_by == 'h':
        return end_time.replace(minute=0, second=0, microsecond=0)
    else:
        return end_time.replace(hour=0, minute=0, second=0, microsecond=0)
