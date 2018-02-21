from __future__ import print_function
from __future__ import absolute_import
import datetime
from django.core.management import BaseCommand
from corehq.util.log import with_progress_bar
from casexml.apps.phone.models import SyncLog, SyncLogSQL, properly_wrap_sync_log, \
    synclog_to_sql_object
from dimagi.utils.couch.database import iter_docs_with_retry


class Command(BaseCommand):
    """
    Migrate couch synclogs to SQL
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--from_date',
            help='Date after which to update xforms (inclusive) (YYYY-MM-DD). Default today')
        parser.add_argument(
            '--to_date',
            help='Date before which to update xforms (exclusive). Default is end of today')
        parser.add_argument(
            '--failfast',
            action='store_true',
            dest='failfast',
            default=False,
            help='Stop processing if there is an error',
        )

    def handle(self, *args, **options):

        assert bool(options.get('to_date')) == bool(options.get('from_date')), "Both from and to dates must be specified or neither"

        if options.get('to_date'):
            datetime.datetime.strptime(options.get('to_date'), "%Y-%m-%d")
            to_date = options.get('to_date')
        else:
            to_date = (datetime.date.today() + datetime.timedelta(days=1)).stftime("%Y-%m-%d")
        if options.get('from_date'):
            datetime.datetime.strptime(options.get('from_date'), "%Y-%m-%d")
            from_date = options.get('from_date')
        else:
            from_date = datetime.datetime.today().stftime("%Y-%m-%d")

        all_sync_log_ids = {
            row['id'] for row in
            SyncLog.view(
                "sync_logs_by_date/view",
                startkey=[from_date],
                endkey=[to_date],
                reduce=False,
                include_docs=False
            )
        }
        already_created_ids = {
            _id.hex for _id in
            SyncLogSQL.objects.filter(date__gte=from_date, date__lt=to_date)
            .values_list('synclog_id', flat=True)
        }
        to_be_created = all_sync_log_ids - already_created_ids
        print("Total {} synclogs found in given date range".format(len(all_sync_log_ids)))
        if to_be_created:
            if already_created_ids:
                print("{} synclogs are already migrated. Migrating the rest".format(
                    len(already_created_ids & all_sync_log_ids)
                ))
            self.migrate_synclog_ids(to_be_created)
        else:
            print("All synclogs in this date range are already migrated")

    def migrate_synclog_ids(self, synclog_ids):
        """
        synclog_ids should be list of couch synclog ids that are not already
            migrated to SQL.
        """
        total_count = len(synclog_ids)
        database = SyncLog.get_db()
        sql_logs = []
        docs = with_progress_bar(iter_docs_with_retry(database, synclog_ids, 500), length=total_count)
        for i, sync_log_dict in enumerate(docs):
            sql_logs.append(
                synclog_to_sql_object(properly_wrap_sync_log(sync_log_dict))
            )
            if i % 100 == 0:
                print('Migrated {}/{} logs'.format(i, total_count))
                SyncLogSQL.objects.bulk_create(sql_logs)
                sql_logs = []
        if sql_logs:
            print('Migrated {}/{} logs'.format(total_count, total_count))
            SyncLogSQL.objects.bulk_create(sql_logs)
