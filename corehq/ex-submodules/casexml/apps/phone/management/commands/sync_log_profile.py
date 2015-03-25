import csv
from django.core.management import BaseCommand
from casexml.apps.phone.models import SyncLog
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    """
    Generate profile output for sync logs.
    """

    def handle(self, filename, *args, **kwargs):
        database = SyncLog.get_db()
        all_sync_log_ids = [
            row['id'] for row in
            database.view('phone/sync_logs_by_user', reduce=False, include_docs=False)
        ]
        total_count = len(all_sync_log_ids)

        headers = [
            'date', 'user', 'cases', 'dependent cases', 'total cases', 'initial', 'duration',
            'duration per case (ms/case)',
        ]

        with open(filename, 'wb') as f:
            writer = csv.writer(f, dialect=csv.excel)
            writer.writerow(
                headers
            )
            for i, sync_log_dict in enumerate(iter_docs(database, all_sync_log_ids, 500)):
                duration = sync_log_dict.get('duration')
                cases = len(sync_log_dict.get('cases_on_phone', []))
                dependent_cases = len(sync_log_dict.get('dependent_cases_on_phone', []))
                total_cases = cases + dependent_cases
                if duration and total_cases:
                    average_time = float(duration) * 1000 / float(total_cases)
                    writer.writerow([
                        (sync_log_dict.get('date') or '1980-01-01')[:10],  # strip times off of the dates
                        sync_log_dict.get('user_id'),
                        cases,
                        dependent_cases,
                        cases + dependent_cases,
                        bool(sync_log_dict.get('previous_log_id')),
                        duration,
                        '{0:.2f}'.format(average_time)

                    ])
                if i % 500 == 0:
                    print 'processed {}/{} logs'.format(i, total_count)
