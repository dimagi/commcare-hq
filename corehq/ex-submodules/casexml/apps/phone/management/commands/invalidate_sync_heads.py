from django.core.management import BaseCommand, CommandError

from casexml.apps.phone.models import SimplifiedSyncLog
from casexml.apps.phone.dbaccessors.sync_logs_by_user import synclog_view


class Command(BaseCommand):
    """
    Forces a 412 for a given user by creating bad state in the all synclogs
    for the given user after the given date
    """
    args = "user_id date"

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError("Usage is ./manage.py invalidate_sync_heads %s" % self.args)
        user_id = args[0]
        date = args[1]
        results = synclog_view(
            "phone/sync_logs_by_user",
            startkey=[user_id, {}],
            endkey=[user_id, date],
            descending=True,
            reduce=False,
            include_docs=True,
        )

        logs = []
        for res in results:
            log = SimplifiedSyncLog.wrap(res['doc'])
            log.case_ids_on_phone = {'broken to force 412'}
            logs.append(log)
        SimplifiedSyncLog.bulk_save(logs)
