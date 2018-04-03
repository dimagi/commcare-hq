from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.apps.reports.models import ReportNotification, ReportConfig
from corehq.apps.userreports.models import ReportConfiguration
from corehq.util.couch import get_document_or_not_found, DocumentNotFound
from collections import defaultdict
from couchdbkit.exceptions import ResourceNotFound
from dimagi.utils.couch.undo import is_deleted


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

        for notification_id in notification_id_iterator:
            notification = ReportNotification.get(notification_id['id'])
            updated_n = False

            for cid in notification.config_ids:
                try:
                    rc = ReportConfig.get(cid)
                    if not rc.subreport_slug:  # seems to be the case of common reports
                        continue

                    rcuration = get_document_or_not_found(
                        ReportConfiguration, rc.domain, rc.subreport_slug)
                    if is_deleted(rcuration):
                        if options['execute']:
                            rc.delete()  # i am updating notifications manually
                        updated_n = True
                except DocumentNotFound:  # ReportConfiguration not found
                    pass

            if updated_n:
                handled_cases += 1
            notifications_sifted += 1

            if notifications_sifted % 100 == 0:
                self.stdout.write("%s%s notifications processed; %s notifications updated" %
                                  (dry_run_prefix, notifications_sifted, handled_cases))

        self.stdout.write(
            "%sFinished cleaning orphaned notifications.\n%s notifications processed; %s notifications updated" %
            (dry_run_prefix, notifications_sifted, handled_cases))
