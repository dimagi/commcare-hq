from __future__ import absolute_import
from django.core.management import BaseCommand

from casexml.apps.phone.models import SimplifiedSyncLog


class Command(BaseCommand):
    """
    Forces a 412 for a given user by creating bad state in the all synclogs
    for the given user after the given date
    """

    def add_arguments(self, parser):
        parser.add_argument('user_id')
        parser.add_argument('date')

    def handle(self, user_id, date, **options):
        results = SimplifiedSyncLog.view(
            "phone/sync_logs_by_user",
            startkey=[user_id, {}],
            endkey=[user_id, date],
            descending=True,
            reduce=False,
            include_docs=True,
        )

        logs = []
        for log in results:
            log.case_ids_on_phone = {'broken to force 412'}
            logs.append(log)
        SimplifiedSyncLog.bulk_save(logs)
