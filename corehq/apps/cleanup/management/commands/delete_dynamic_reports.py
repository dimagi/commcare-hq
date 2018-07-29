from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from six.moves import input


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('report_type')

    def handle(self, report_type, **options):
        if input(
                'Really delete all reports of type {}? (y/n)\n'.format(report_type)).lower() == 'y':
            for domain in Domain.get_all():
                save_domain = False
                for report_config in domain.dynamic_reports:
                    old_report_count = len(report_config.reports)
                    report_config.reports = [r for r in report_config.reports if r.report != report_type]
                    if len(report_config.reports) != old_report_count:
                        save_domain = True
                if save_domain:
                    print('removing reports from {}'.format(domain.name))
                    domain.save()
        else:
            print('aborted')
