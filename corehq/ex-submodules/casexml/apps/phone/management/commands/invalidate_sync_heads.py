from __future__ import absolute_import
from __future__ import unicode_literals
from django_bulk_update.helper import bulk_update as bulk_update_helper
from django.core.management import BaseCommand

from casexml.apps.phone.models import SyncLogSQL, SimplifiedSyncLog, LOG_FORMAT_SIMPLIFY, \
    properly_wrap_sync_log


class Command(BaseCommand):
    """
    Forces a 412 for a given user by creating bad state in the all synclogs
    for the given user after the given date
    """

    def add_arguments(self, parser):
        parser.add_argument('user_id')
        parser.add_argument('date')

    def handle(self, user_id, date, **options):
        # SQL
        synclogs_sql = SyncLogSQL.objects.filter(
            user_id=user_id,
            date=date,
            log_format=LOG_FORMAT_SIMPLIFY
        )
        for synclog in synclogs_sql:
            doc = properly_wrap_sync_log(synclog.doc)
            doc.case_ids_on_phone = {'broken to force 412'}
        bulk_update_helper(synclogs_sql)
