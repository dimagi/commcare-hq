import random
from uuid import uuid4

from django.core.management.base import BaseCommand

from shapely.geometry import Point, Polygon

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.couch.database import get_safe_write_kwargs

from corehq.apps.geospatial.utils import (
    get_geo_case_property,
    get_geo_user_property,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser

CASE_TYPE = 'test-case'
CASE_BLOCK_CHUNK_SIZE = 1000
SCRIPT_NAME = 'corehq.apps.geospatial...create_test_metadata'


class Command(BaseCommand):
    help = 'Create geo-located test data'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('users', type=int)
        parser.add_argument('cases', type=int)

    def handle(self, *args, **options):
        domain = options['domain']
        num_users = options['users']
        num_cases = options['cases']

        self.stdout.write(f'Creating {num_users} users for domain {domain}')
        create_users(domain, num_users)

        self.stdout.write(f'Creating {num_cases} cases for domain {domain}')
        create_cases(domain, num_cases)


def create_users(domain, num_users):
    geo_property = get_geo_user_property(domain)
    for __ in range(num_users):
        create_user(domain, geo_property)


def create_user(domain, geo_property):
    random_point = random_point_in_scotland()
    random_suffix = random.randint(10_000, 99_999)
    username = '.'.join((
        random.choice(FIRST_NAMES),
        random.choice(LAST_NAMES),
        str(random_suffix),
    ))
    mobile_username = f'{username}@{domain}.commcarehq.org'
    password = '123'
    user = CommCareUser.create(
        domain,
        mobile_username,
        password,
        created_by=None,
        created_via=SCRIPT_NAME,
        user_data={geo_property: f'{random_point.y} {random_point.x} 0 0'},
        commiit=False,  # Save below to avoid logging
    )
    user.save(**get_safe_write_kwargs())


def random_point_in_scotland():
    min_x, min_y, max_x, max_y = ROUGHLY_SCOTLAND.bounds
    while True:
        random_x = random.uniform(min_x, max_x)
        random_y = random.uniform(min_y, max_y)
        random_point = Point(random_x, random_y)
        if ROUGHLY_SCOTLAND.contains(random_point):
            return random_point


def create_cases(domain, num_cases):
    geo_property = get_geo_case_property(domain)
    i = 0
    case_blocks = []
    while True:
        if i == num_cases:
            break
        i += 1
        case_blocks.append(get_case_block(geo_property))
        if not i % CASE_BLOCK_CHUNK_SIZE:
            submit_chunk(domain, case_blocks)
            case_blocks = []
    if case_blocks:
        submit_chunk(domain, case_blocks)


def get_case_block(geo_property):
    case_id = uuid4().hex
    case_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
    random_point = random_point_in_scotland()
    return CaseBlock(
        case_id=case_id,
        case_type=CASE_TYPE,
        case_name=case_name,
        create=True,
        update={geo_property: f'{random_point.y} {random_point.x} 0 0'},
    )


def submit_chunk(domain, case_blocks):
    submit_case_blocks(
        [cb.as_text() for cb in case_blocks],
        domain,
        device_id=SCRIPT_NAME,
    )


ROUGHLY_SCOTLAND = Polygon([  # Sorry all of the islands
    (58.421036, -4.910423),
    (58.589584, -3.165290),
    (57.449559, -4.344813),
    (57.622931, -1.927251),
    (55.945067, -3.356255),
    (55.802299, -2.093642),
    (55.802299, -2.093642),
])


FIRST_NAMES = [
    'Aaliyah',
    'Aaron',
    'Abigail',
    'Addison',
    'Aiden',
    'Alexander',
    'Amelia',
    'Andrew',
    'Anthony',
    'Aria',
    'Aubrey',
    'Audrey',
    'Aurora',
    'Ava',
    'Avery',
    'Bella',
    'Benjamin',
    'Brooklyn',
    'Caleb',
    'Carter',
    'Charles',
    'Charlotte',
    'Chloe',
    'Christian',
    'Christopher',
    'Claire',
    'Connor',
    'Daniel',
    'David',
    'Dylan',
    'Eli',
    'Ella',
    'Ellie',
    'Emma',
    'Ethan',
    'Evelyn',
    'Gabriel',
    'Genesis',
    'Grace',
    'Grayson',
    'Hannah',
    'Harper',
    'Hazel',
    'Henry',
    'Hunter',
    'Isaac',
    'Isabella',
    'Isaiah',
    'Jack',
    'Jackson',
    'James',
    'Jameson',
    'Jaxon',
    'John',
    'Joseph',
    'Joshua',
    'Julian',
    'Kennedy',
    'Kinsley',
    'Landon',
    'Layla',
    'Leah',
    'Levi',
    'Liam',
    'Lillian',
    'Lily',
    'Lincoln',
    'Logan',
    'Lucas',
    'Lucy',
    'Luke',
    'Madison',
    'Matthew',
    'Mia',
    'Michael',
    'Mila',
    'Natalie',
    'Nathan',
    'Noah',
    'Nora',
    'Olivia',
    'Owen',
    'Paisley',
    'Penelope',
    'Riley',
    'Ryan',
    'Samantha',
    'Samuel',
    'Savannah',
    'Scarlett',
    'Sebastian',
    'Skylar',
    'Sophia',
    'Stella',
    'Thomas',
    'Victoria',
    'Violet',
    'William',
    'Wyatt',
    'Zoey',
]

LAST_NAMES = [
    'Anderson',
    'Brown',
    'Cameron',
    'Campbell',
    'Davis',
    'Duncan',
    'Ferguson',
    'Fraser',
    'Garcia',
    'Gonzalez',
    'Graham',
    'Hamilton',
    'Harris',
    'Henderson',
    'Hernandez',
    'Jackson',
    'Johnson',
    'Johnston',
    'Jones',
    'Lee',
    'Lopez',
    'MacDonald',
    'MacKenzie',
    'MacLeod',
    'Martin',
    'Martinez',
    'Miller',
    'Moore',
    'Morrison',
    'Murray',
    'Paterson',
    'Perez',
    'Reid',
    'Robertson',
    'Rodriguez',
    'Ross',
    'Scott',
    'Sinclair',
    'Smith',
    'Stewart',
    'Sutherland',
    'Taylor',
    'Thomas',
    'Thompson',
    'Thomson',
    'Wallace',
    'White',
    'Williams',
    'Wilson',
    'Young',
]
