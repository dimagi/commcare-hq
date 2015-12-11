import csv
from django.core.management.base import BaseCommand
import sys
from corehq.apps.domain.models import Domain


class Command(BaseCommand):

    def handle(self, *args, **options):
        if len(args) != 1:
            print 'usage is ./manage.py list_dynamic_reports filename'
            sys.exit(1)
        filename = args[0]
        with open(filename, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(['domain', 'section', 'type', 'report'])
            for domain in Domain.get_all():
                for report_config in domain.dynamic_reports:
                    for report in report_config.reports:
                        writer.writerow([domain.name, report_config.section_title, report.report, report.name])
