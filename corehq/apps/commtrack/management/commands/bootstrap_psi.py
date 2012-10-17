from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.helpers import *
import sys

PRODUCTS = [
    ('PSI kit', 'k'),
    ('non-PSI kit', 'nk'),
]

class Command(BaseCommand):
    args = 'domain'
    option_list = BaseCommand.option_list + (
        make_option('-f', '--force', action='store_true', dest='force', default=False,
                    help='force bootstrapping of domain, even if already appears set up'),
        )
    help = 'Initialize commtrack config for PSI'

    def handle(self, *args, **options):
        try:
            domain_name = args[0]
        except IndexError:
            self.stderr.write('domain required\n')
            return

        self.stdout.write('Bootstrapping commtrack for domain [%s]\n' % domain_name)

        domain = Domain.get_by_name(domain_name)
        if domain.commtrack_enabled:
            if options['force']:
                self.stderr.write('Warning: this domain appears to be already set up.\n')                
            else:
                self.stderr.write('Aborting: this domain has already been set up.\n')
                return

        commtrack_enable_domain(domain)
        make_psi_config(domain.name)
        make_products(domain.name, PRODUCTS)

def commtrack_enable_domain(domain):
    domain.commtrack_enabled = True
    domain.save()

def make_products(domain, products):
    for name, code in products:
        make_product(domain, name, code)

        # locations
        # supply point cases and subcases
        # users and verified contacts
