import csv
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.helpers import make_supply_point
from dimagi.utils.couch.database import get_db

def import_locations(domain, f):
    data = list(csv.DictReader(f))
    messages = []
    for loc in data:
        messages.extend(import_location(domain, loc))
    return messages

def import_location(domain, loc):
    messages = []

    def _loc(*args, **kwargs):
        return make_loc(domain, *args, **kwargs)

    def get_by_name(loc_name, loc_type, parent):
        # TODO: could cache the results of this for speed
        existing = Location.filter_by_type(domain, loc_type, parent)
        try:
            return [l for l in existing if l.name == loc_name][0]
        except IndexError:
            return None

    HIERARCHY_FIELDS = ('state', 'district', 'block')
    hierarchy = [(p, loc[p]) for p in HIERARCHY_FIELDS]

    # create parent hierarchy if it does not exist
    parent = None
    for anc_type, anc_name in hierarchy:
        child = get_by_name(anc_name, anc_type, parent)
        if not child:
            child = _loc(name=anc_name, location_type=anc_type, parent=parent)
            messages.append('created %s %s' % (anc_type, anc_name))
        parent = child

    name = loc['outlet_name']
    # check if outlet already exists
    outlet = get_by_name(name, 'outlet', parent)
    if outlet:
        messages.append('outlet %s exists; skipping...' % name)
    else:
        outlet_props = dict(loc)
        for k in ('outlet_name', 'outlet_code'):
            del outlet_props[k]

        # check that sms code for outlet is unique
        code = loc['outlet_code'].lower()
        if get_db().view('commtrack/locations_by_code',
                         key=[domain, code],
                         include_docs=True).one():
            messages.append('code %s for outlet %s already in use! outlet NOT created' % (code, name))
        else:
            outlet = _loc(name=name, location_type='outlet', parent=parent, **outlet_props)
            make_supply_point(domain, outlet, code)
            messages.append('created outlet %s' % name)

    return messages

def make_loc(domain, *args, **kwargs):
    loc = Location(domain=domain, *args, **kwargs)
    loc.save()
    return loc


# old code for generating random location hierarchy -- shelving for now

"""

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

"""
