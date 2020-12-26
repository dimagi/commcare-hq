from inspect import cleandoc

from django.core.management.base import BaseCommand

from corehq.util.log import with_progress_bar

from ...dbaccessors import (
    get_domains_that_have_repeat_records,
    iter_repeat_records_by_domain,
    prefetch_attempts,
)
from ...models import SQLRepeatRecord
from ...tasks import migrate_to_couch, revert_migrated


class Command(BaseCommand):
    help = cleandoc("""
    Management command for rolling back RepeatRecord migration to SQL:

    1. Revert the "🚀" PR that contains the following commits:

       * "🚀 Repeater.register() registers a SQLRepeatRecord"
       * "🚀 Migrate repeat records"
       * "🚀 Call process_repeater() from check_repeaters()"

    2. Execute this management command to unset the RepeatRecord
       "migrated" state. This command can be executed multiple times if
       execution fails due to ResourceConflict errors.


    To try switching to SQL again:

    1. Drop and recreate the SQL tables::

           $ ./manage.py migrate repeaters 0001
           $ ./manage.py migrate repeaters

    2. Redeploy the "🚀" PR.

    """)

    def handle(self, *args, **options):
        print('Reverting migrated Couch records')
        for couch_record in iter_migrated_records():
            revert_migrated.delay(couch_record)
        print('Migrating new SQL records to Couch')
        sql_records, count = new_sql_records()
        for sql_record in with_progress_bar(sql_records, length=count):
            migrate_to_couch.delay(sql_record)


def iter_migrated_records():
    domains = get_domains_that_have_repeat_records()
    for domain in with_progress_bar(domains):
        for record in iter_repeat_records_by_domain(domain):
            # "repeaters/repeat_records" Couch view would need to be
            # reindexed for iter_repeat_records_by_domain() to support
            # state='MIGRATED'. Rather just check state here:
            if record.migrated:
                yield record


def new_sql_records():
    queryset = (SQLRepeatRecord.objects
                .filter(couch_id__isnull=True)
                .select_related('repeater_stub'))
    count = queryset.count()
    records = prefetch_attempts(queryset, count)
    return records, count
