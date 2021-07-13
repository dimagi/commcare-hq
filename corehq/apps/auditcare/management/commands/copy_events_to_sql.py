from corehq.util import soft_assert
from django.core.management.base import BaseCommand

import gevent

from corehq.apps.auditcare.couch_to_sql import copy_events_to_sql
from corehq.apps.auditcare.utils.migration import AuditCareMigrationUtil
from dimagi.utils.logging import notify_exception


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
        try:
            while True:
                if options['only_errored']:
                    batches = util.get_errored_keys(5)
                    if not batches:
                        print("No errored keys present")
                        return
                else:
                    batches = util.generate_batches(workers, batch_by)
                if not batches:
                    print("No batches to process")
                    return
                batched_processes = [gevent.spawn(copy_events_to_sql, *batch) for batch in batches]
                gevent.joinall([*batched_processes])
        except Exception as e:
            message = f"Error in copy_events_to_sql while generating batches\n{e}"
            notify_exception(None, message=message)
            _soft_assert = soft_assert(to="{}@{}.com".format('aphulera', 'dimagi'), notify_admins=False)
            _soft_assert(False, message)
            return
