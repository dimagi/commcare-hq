from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import csv
from django.core.management.base import BaseCommand
import sys
from corehq.apps.domain.models import Domain


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, filename, **options):
        with open(filename, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(['domain', 'section', 'type', 'report'])
            for domain in Domain.get_all():
                for report_config in domain.dynamic_reports:
                    for report in report_config.reports:
                        writer.writerow([domain.name, report_config.section_title, report.report, report.name])
