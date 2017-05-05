from __future__ import print_function

from django.core.management.base import BaseCommand

from corehq.apps.data_dictionary.util import generate_data_dictionary, OldExportsEnabledException
from corehq.apps.domain.models import Domain
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    """
        Generates data dictionary for all domains
    """
    help = 'Generates data dictionary for all domains'

    def handle(self, **options):
        print('Generating data dictionary for domains')
        failed_domains = []
        for domain_dict in with_progress_bar(Domain.get_all(include_docs=False)):
            domain = domain_dict['key']
            try:
                generate_data_dictionary(domain)
            except OldExportsEnabledException:
                failed_domains.append(domain)
        print('--- Failed Domains ---')
        for domain in failed_domains:
            print(domain)
