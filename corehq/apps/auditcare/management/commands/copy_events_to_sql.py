from django.core.management.base import BaseCommand

import gevent

from corehq.apps.auditcare.tasks import copy_events_to_sql
from corehq.apps.auditcare.utils.migration import AuditCareMigrationUtil


class Command(BaseCommand):
    help = """Copy audit data from couch to sql"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--workers',
            default=1,
            type=int,
            help="Number of concurrent workers, defaults to 1"
        )
        parser.add_argument(
            '--batch_by',
            default='h',
            choices=['h', 'd'],
            help="Execution can be batched in hours or days. Defaults to hour"
        )
        parser.add_argument(
            '--only_errored',
            default=False,
            type=bool,
            choices=[True, False],
            help="Will try to process batches that have been errored"
        )

    def handle(self, **options):
        workers = options['workers']
        batch_by = options['batch_by']
        util = AuditCareMigrationUtil()
        batches = []
        while True:
            if options['only_errored']:
                if util.total_errored_keys() > 0:
                    batches = util.get_errored_keys(5)
                else:
                    print("No errored keys present")
                    exit(1)
            else:
                batches = self.generate_batches(workers, batch_by)
            batched_processes = [gevent.spawn(copy_events_to_sql, *batch) for batch in batches]
            gevent.joinall([*batched_processes])

        #count = copy_events_to_sql(int(limit))

    def generate_batches(self, worker_count, batch_by):
        migration_util = AuditCareMigrationUtil()
        start_datetime = migration_util.get_next_batch_start()
        migration_util.acquire_read_lock()
        if not start_datetime:
            # for the first call
            start_datetime = INITIAL_START_DATE

        start_time = _get_formatted_start_time(start_datetime, batch_by)
        end_time = None
        batches = []
        for index in range(worker_count):
            end_time = _get_end_time(start_time, batch_by)
            batches.append([start_time, end_time])
            start_time = end_time
        migration_util.set_next_batch_start(end_time)
        migration_util.release_read_lock()
        if end_time > datetime.now():
            print("Migration successfully done")
            exit(1)
        return batches


def _get_end_time(start_time, batch_by):
    delta = timedelta(hours=1) if batch_by == 'h' else timedelta(days=1)
    return start_time + delta


def _get_formatted_start_time(start_time, batch_by):
    if batch_by == 'h':
        return start_time.replace(minute=0, second=0, microsecond=0)
    else:
        return start_time.replace(hour=0, minute=0, second=0, microsecond=0)
