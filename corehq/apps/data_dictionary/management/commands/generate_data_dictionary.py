from __future__ import print_function

from django.core.management.base import BaseCommand
from jsonobject.exceptions import WrappingAttributeError

from corehq.apps.data_dictionary.util import generate_data_dictionary, OldExportsEnabledException
from corehq.apps.domain.models import Domain
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    """
        Generates data dictionary for all domains
    """
    help = 'Generates data dictionary for all domains'

    def handle(self, *args, **options):
        print('Generating data dictionary for domains')
        old_export_domains = []
        failed_wrap = []
        for domain_dict in with_progress_bar(Domain.get_all(include_docs=False)):
            domain = domain_dict['key']
            try:
                generate_data_dictionary(domain)
            except OldExportsEnabledException:
                old_export_domains.append(domain)
            except WrappingAttributeError as e:
                failed_wrap.append((domain, unicode(e)))
        print('--- Old Export Domains ---')
        for domain in old_export_domains:
            print(domain)
        print('--- Failed Wrap Domains ---')
        for domain, error in failed_wrap:
            print('{}: {}'.format(domain, error))
