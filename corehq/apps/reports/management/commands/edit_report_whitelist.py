from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = 'Reindex a pillowtop index'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'reports',
            nargs='*'
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
        domain = Domain.get_by_name(domain)

        if reset:
            domain.report_whitelist = []

        for report in reports:
            domain.report_whitelist.append(report)
        domain.save()