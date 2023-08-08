from django.core.management.base import BaseCommand

from corehq.apps.data_dictionary.util import generate_data_dictionary
from corehq.apps.domain.models import Domain
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = 'Generates data dictionary for any or all domains'

    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='*',
            help="Domain name(s). If blank, will generate for all domains")

    def handle(self, **options):
        failed_domains = []
        domains = options['domains'] or [d['key'] for d in Domain.get_all(include_docs=False)]
        print('Generating data dictionary for {} domains'.format(len(domains)))
        for domain in with_progress_bar(domains):
            try:
                generate_data_dictionary(domain)
            except Exception:
                failed_domains.append(domain)
        print('--- Failed Domains ---')
        for domain in failed_domains:
            print(domain)
