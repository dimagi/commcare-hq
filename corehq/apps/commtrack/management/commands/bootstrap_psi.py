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

STATES = [
    'Andra Predesh',
    'Bihar',
    'Jammu and Kashmir',
    'Karnataka',
    'Punjab',
    'Rajasthan',
    'Tamil Nadu',
]

DISTRICTS = {
    'Andra Predesh': [
        'Anantapur',
        'Chittoor',
        'East Godavari',
        'Hyderabad',
        'Khammam',
        'Medak',
        'Prakasam',
        'Srikakulam',
        'Vizianagaram',
        'West Godavari'
    ],
    'Bihar': [
        'Buxar',
        'Darbhanga',
        'Gaya',
        'Jamui',
        'Lakhisarai',
        'Muzaffarpur',
        'Nawada',
        'Pashchim Champaran',
        'Saran',
        'Vaishali'
    ],
    'Jammu and Kashmir': [
        'Anantnag',
        'Badgam',
        'Doda',
        'Jammu',
        'Kupwara',
        'Leh',
        'Poonch',
        'Rajauri',
        'Srinagar',
        'Udhampur'
    ],
    'Karnataka': [
        'Bagalkot',
        'Chitradurga',
        'Davanagere',
        'Gadag',
        'Haveri',
        'Kodagu',
        'Mysore',
        'Raichur',
        'Shimoga',
        'Uttara Kannada'
    ],
    'Punjab': [
        'Amritsar',
        'Bathinda',
        'Firozpur',
        'Gurdaspur',
        'Jalandhar',
        'Ludhiana',
        'Mansa',
        'Patiala',
        'Rupnagar',
        'Sangrur'
    ],
    'Rajasthan': [
        'Ajmer',
        'Banswara',
        'Dausa',
        'Ganganagar',
        'Jaipur',
        'Karauli',
        'Nagaur',
        'Pali',
        'Sikar',
        'Udaipur'
    ],
    'Tamil Nadu': [
        'Ariyalur',
        'Coimbatore',
        'Dindigul',
        'Erode',
        'Kanyakumari',
        'Nagapattinam',
        'Pudukkottai',
        'Sivaganga',
        'Tiruvannamalai',
        'Villupuram'
    ]
}

LOC_BRANCH_FACTOR = 23

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

    def every_time_setup(self, domain, **kwargs):
        self.stderr.write('Refreshing...\n')
        # nothing to do
        pass

def commtrack_enable_domain(domain):
    domain.commtrack_enabled = True
    domain.save()

def make_products(domain, products):
    for name, code in products:
        make_product(domain, name, code)

SAMPLE_VILLAGES = [
    'Abhayapuri',
    'Bathinda',
    'Colgong',
    'Gobranawapara',
    'Jayankondam',
    'Karimganj',
    'Mahendragarh',
    'Pallikonda',
    'Rajahmundry',
    'Srikakulam',
]

OUTLET_TYPES = [
    'rural',
    'peri-urban',
    'urban',
    'orbital',
]

def fake_phone_number(length):
    prefix = '099'
    return prefix + ''.join(str(random.randint(0, 9)) for i in range(length - len(prefix)))

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
                    properties = {
                        'state': state_name,
                        'district': district_name,
                        'block': block_name,
                        'village': random.choice(SAMPLE_VILLAGES),
                        'outlet_id': outlet_id,
                        'outlet_type': random.choice(OUTLET_TYPES),
                        'contact_phone': fake_phone_number(10),
                    }
                    outlet = make_loc(name=outlet_name, location_type='outlet', parent=block, **properties)
                    outlet_code = '%d%d%d%d' % (i + 1, j + 1, k + 1, l + 1)
                    make_supply_point(domain, outlet, outlet_code)


