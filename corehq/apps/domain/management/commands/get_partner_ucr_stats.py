from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand

from corehq.apps.userreports.models import (
    report_config_id_is_static,
    StaticReportConfiguration,
    ReportConfiguration,
)
from corehq.util.couch import get_document_or_not_found


class Command(BaseCommand):
    help = "Give stats on ucr downloads based on logs"
    slug = 'ucr_stats_for_partners'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="domain name",
        )
        parser.add_argument(
            'ucr_ids',
            help="comma separated list of export_ids",
        )

    def handle(self, domain, ucr_ids, **options):
        self.stdout.write('export id\texport type\tproject\texport name\tapp id\tapp name')
        ucr_ids = ucr_ids.split(',')
        for ucr_id in ucr_ids:
            self.print_ucr_info(ucr_id, domain)

    def print_ucr_info(self, ucr_id, domain):
        try:
            report_config = self.get_ucr_config(ucr_id, domain)
            report_title = report_config.title
        except ResourceNotFound:
            report_title = "not found (deleted)"

        self.stdout.write(f'{ucr_id}\t{domain}\t{report_title}')

    def get_ucr_config(self, ucr_id, domain):
        if report_config_id_is_static(ucr_id):
            return StaticReportConfiguration.by_id(ucr_id, domain=domain)
        else:
            return get_document_or_not_found(ReportConfiguration, domain, ucr_id)
