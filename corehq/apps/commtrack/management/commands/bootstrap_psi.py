from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CommCareUser
from corehq.apps.commtrack.helpers import *
import sys
import random

PRODUCTS = [
    ('PSI kit', 'k'),
    ('non-PSI kit', 'nk'),
]

STATES = [
    'Andra Predesh',
    'Karnataka',
    'Tamil Nadu',
]

DISTRICTS = {
    'Andra Predesh': [
        'Hyderabad',
        'Medak',
        'Vizianagaram',
    ],
    'Karnataka': [
        'Davanagere',
        'Mysore',
        'Uttara Kannada',
    ],
    'Tamil Nadu': [
        'Chennai',
        'Vuddalore',
        'Theni',
    ],
}    

LOC_BRANCH_FACTOR = 3

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
            self.one_time_setup(domain)
        self.every_time_setup(domain)

    def one_time_setup(self, domain):
        self.stderr.write('Setting up domain from scratch...\n')
        commtrack_enable_domain(domain)
        make_psi_config(domain.name)
        make_products(domain.name, PRODUCTS)
        create_locations(domain.name)

    def every_time_setup(self, domain):
        self.stderr.write('Refreshing...\n')
        register_reporters(domain.name)

def commtrack_enable_domain(domain):
    domain.commtrack_enabled = True
    domain.save()

def make_products(domain, products):
    for name, code in products:
        make_product(domain, name, code)

def create_locations(domain):
    def make_loc(*args, **kwargs):
        loc = Location(domain=domain, *args, **kwargs)
        loc.save()
        return loc

    for i, state_name in enumerate(STATES):
        state = make_loc(name=state_name, location_type='state')
        for j, district_name in enumerate(DISTRICTS[state_name]):
            district = make_loc(name=district_name, location_type='district', parent=state)
            for k in range(random.randint(1, LOC_BRANCH_FACTOR)):
                block_id = '%s%s-%d' % (state_name[0], district_name[0], k + 1)
                block_name = 'Block %s' % block_id
                block = make_loc(name=block_name, location_type='block', parent=district)
                for l in range(random.randint(1, LOC_BRANCH_FACTOR)):
                    outlet_id = '%s%s' % (block_id, chr(ord('A') + l))
                    outlet_name = 'Outlet %s' % outlet_id
                    outlet = make_loc(name=outlet_name, location_type='outlet', parent=block)
                    outlet_code = '%d%d%d%d' % (i + 1, j + 1, k + 1, l + 1)
                    make_supply_point(domain, outlet, outlet_code)

def register_reporters(domain):
    mobile_workers = CommCareUser.view('users/phone_users_by_domain',
                                       startkey=[domain],
                                       endkey=[domain, {}],
                                       include_docs=True)
    for mw in mobile_workers:
        make_verified_contact(mw.username)
