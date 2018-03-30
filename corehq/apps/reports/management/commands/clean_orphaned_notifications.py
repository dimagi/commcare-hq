from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.apps.reports.models import ReportNotification, ReportConfig
from collections import defaultdict
from couchdbkit.exceptions import ResourceNotFound


class Command(BaseCommand):
    help = "Delete reports.models.ReportNotification's without reports.models.ReportConfig's"

    def add_arguments(self, parser):
        parser.add_argument('-x', '--execute', action='store_true',
                            help='actually make the change; otherwise just a dry run')

    def handle(self, **options):
        handled_cases = 0
        notifications_sifted = 0
        dry_run_prefix = "" if options['execute'] else ">>>>>>>DRY RUN\t"

        notification_id_iterator = ReportNotification.view(
            "reportconfig/all_notifications",
            reduce=False,
            include_docs=False
        )

        existent_config_ids = defaultdict(lambda: False)
        for notification_id in notification_id_iterator:
            nid = notification_id['id']
            notification = ReportNotification.get(nid)
            updated_notification = False

            for cid in notification.config_ids:
                if not existent_config_ids[cid]:
                    try:
                        ReportConfig.get(cid)
                        existent_config_ids[cid] = True
                    except ResourceNotFound:
                        notification.config_ids.remove(cid)
                        updated_notification = True

            if updated_notification:
                if options['execute']:
                    if notification.config_ids:
                        notification.save()
                    else:
                        notification.delete()
                handled_cases += 1
            notifications_sifted += 1

            if notifications_sifted % 100 == 0:
                self.stdout.write("%s%s notifications processes; %s notifications updated" %
                                  (dry_run_prefix, notifications_sifted, handled_cases))

        self.stdout.write(
            "%sFinished cleaning orphaned notifications.\n%s notifications processed; %s notifications updated" %
            (dry_run_prefix, notifications_sifted, handled_cases))
