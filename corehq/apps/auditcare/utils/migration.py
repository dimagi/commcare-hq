import logging

from datetime import datetime, timedelta

from django.core.cache import cache

from dimagi.utils.dates import force_to_datetime

from corehq.apps.auditcare.models import AuditcareMigrationMeta, NavigationEventAudit

CUTOFF_TIME = datetime(2012, 12, 31)
CACHE_TTL = 14 * 24 * 60 * 60  # 14 days

logger = logging.getLogger(__name__)


def get_sql_start_date():
    """Get the date of the first SQL auditcare record

    HACK this uses `NavigationEventAudit` since that model is likely to
    have the record with the earliest timestamp.

    NOTE this function assumes no SQL data has been archived, and that
    all auditcare data in Couch will be obsolete and/or archived before
    SQL data. It should be removed when the data in Couch is no longer
    relevant.
    """
    manager = NavigationEventAudit.objects
    row = manager.order_by("event_date").values("event_date")[:1].first()
    return row["event_date"] if row else datetime.utcnow()


class AuditCareMigrationUtil():

    def __init__(self):
        self.start_key = "auditcare_migration_2021_next_batch_time"
        self.start_lock_key = "auditcare_migration_batch_lock"

    def get_next_batch_start(self):
        return cache.get(self.start_key)

    def generate_batches(self, worker_count, batch_by):
        batches = []
        with cache.lock(self.start_lock_key, timeout=10):
            start_datetime = self.get_next_batch_start()
            if not start_datetime:
                if AuditcareMigrationMeta.objects.count() != 0:
                    raise MissingStartTimeError()
                # For first run set the start_datetime to the event_time of the first record
                # in the SQL. If there are no records in SQL, start_time would be set as
                # current time
                start_datetime = get_sql_start_date()
                if not start_datetime:
                    start_datetime = datetime.now()

            if start_datetime < CUTOFF_TIME:
                logger.info("Migration Successfull")
                return

            start_time = start_datetime
            end_time = None

            for index in range(worker_count):
                end_time = _get_end_time(start_time, batch_by)
                if end_time < CUTOFF_TIME:
                    break
                batches.append([start_time, end_time])
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

    def get_cancelled_keys(self, limit=5):
        cancelled_keys = (AuditcareMigrationMeta.objects
            .filter(state=AuditcareMigrationMeta.STARTED, finished_at__isnull=True)
            .values_list('key', flat=True)[:limit]
        )
        return [get_datetimes_from_key(key) for key in cancelled_keys]

    def log_batch_start(self, key):
        if AuditcareMigrationMeta.objects.filter(key=key):
            return
        AuditcareMigrationMeta.objects.create(
            key=key,
            state=AuditcareMigrationMeta.STARTED,
            created_at=datetime.now()
        )

    def set_batch_as_finished(self, key, count, other_doc_type_count=0):
        AuditcareMigrationMeta.objects.filter(key=key).update(
            state=AuditcareMigrationMeta.FINISHED,
            record_count=count,
            other_doc_type_count=other_doc_type_count,
            finished_at=datetime.now()
        )

    def set_batch_as_errored(self, key, last_doc=None, other_doc_type_count=0):
        AuditcareMigrationMeta.objects.filter(key=key).update(
            state=AuditcareMigrationMeta.ERRORED,
            last_doc_processed=last_doc,
            other_doc_type_count=other_doc_type_count
        )

    def get_existing_count(self, key):
        counts = AuditcareMigrationMeta.objects.filter(key=key).values_list(
            'record_count',
            'other_doc_type_count',
        ).first()
        return list(counts) if counts else [0, 0]


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


class MissingStartTimeError(Exception):
    message = """The migration process has already been started before
        But we are unable to determine start key.
        You can manually set the start key using
        
        from datetime import datetime
        from corehq.apps.auditcare.utils.migration import AuditCareMigrationUtil
        start_key = datetime(2021,6,1)  # customize date as necessary
        AuditCareMigrationUtil().set_next_batch_start(start_key)"""

    def __init__(self, message=message):
        super().__init__(message)
