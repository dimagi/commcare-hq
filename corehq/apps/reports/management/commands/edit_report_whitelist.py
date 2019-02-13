from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = 'Adds reports to a projects report whitelist or resets that list'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'reports',
            nargs='*',
            help='report slugs of the reports to add'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            dest='reset',
            default=False,
            help='Clear whitelist before adding new reports.'
        )

    def handle(self, domain, reports, **options):
        reset = options.pop('reset')
        domain_obj = Domain.get_by_name(domain)

        if reset:
            domain_obj.report_whitelist = []

        for report in reports:
            domain_obj.report_whitelist.append(report)
        domain_obj.save()
