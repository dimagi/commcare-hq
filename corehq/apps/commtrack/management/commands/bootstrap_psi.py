from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms.mixin import MobileBackend
from corehq.apps.commtrack.helpers import *
import sys
import random

PRODUCTS = [
    ('PSI kit', 'k'),
    ('non-PSI kit', 'nk'),
    ('ORS', 'o'),
    ('Zinc', 'z'),
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
        if domain is None:
            self.stderr.write('Can\'t find domain\n')
            return
        first_time = True
        if domain.commtrack_enabled:
            self.stderr.write('This domain has already been set up.\n')
            first_time = False
            if options['force']:
                self.stderr.write('Warning: forcing re-init...\n')
                first_time = True

        if first_time:
            self.stderr.write('Setting up domain from scratch...\n')
            one_time_setup(domain)
        self.stderr.write('Refreshing...\n')
        every_time_setup(domain)

def one_time_setup(domain):
    commtrack_enable_domain(domain)
    make_psi_config(domain.name)
    make_products(domain.name, PRODUCTS)

def every_time_setup(domain, **kwargs):
    # nothing to do
    pass

def commtrack_enable_domain(domain):
    domain.commtrack_enabled = True
    domain.save()

def make_products(domain, products):
    for name, code in products:
        make_product(domain, name, code)

