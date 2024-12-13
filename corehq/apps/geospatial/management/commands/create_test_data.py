"""
Create geo-located mobile workers and geo-located cases for testing
national-scale bulk disbursement for microplanning.

This script uses Faker and Shapely, which are not installed in
production environments.

To use this management command, do a limited-release deploy, and then
install the additional requirements in its virtualenv. e.g. ::

    $ cchq --control staging deploy commcare \
           --private \
           --limit='django_manage[0]' \
           --keep-days=7 \
           --commcare-rev=nh/test_data
    ...
    Your private release is located here:
    /home/cchq/www/staging/releases/2024-12-11_15.07

    $ cchq staging tmux 'django_manage[0]'

    cchq:~$ cd www/staging/releases/2024-12-11_15.07
    cchq:~$ source python_env/bin/activate
    cchq:~$ pip install Faker
    cchq:~$ pip install shapely

The django_manage machine has two cores. To execute the management
command on both cores, simply run the command in two tmux windows.

"""
import random
from uuid import uuid4

from django.core.management.base import BaseCommand

from faker import Faker
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
        parser.add_argument('users', type=nonnegative_int)
        parser.add_argument('cases', type=nonnegative_int)

    def handle(self, *args, **options):
        domain = options['domain']
        num_users = options['users']
        num_cases = options['cases']

        self.stdout.write(f'Creating {num_users} users for domain {domain}')
        create_users(domain, num_users)

        self.stdout.write(f'Creating {num_cases} cases for domain {domain}')
        create_cases(domain, num_cases)


def nonnegative_int(value):
    value = int(value)
    if value < 0:
        raise ValueError('Value must be positive or zero')
    return value


def create_users(domain, num_users):
    geo_property = get_geo_user_property(domain)
    for __ in range(num_users):
        create_user(domain, geo_property)


def create_user(domain, geo_property):
    fake = Faker()
    first_name = fake.first_name()
    last_name = fake.last_name()
    random_suffix = str(random.randint(10_000, 99_999))
    username = '.'.join((first_name, last_name, random_suffix))
    mobile_username = f'{username}@{domain}.commcarehq.org'
    password = '123'
    random_point = random_point_in_scotland()
    user = CommCareUser.create(
        domain,
        mobile_username,
        password,
        created_by=None,
        created_via=SCRIPT_NAME,
        first_name=first_name,
        last_name=last_name,
        user_data={geo_property: f'{random_point.y} {random_point.x} 0 0'},
        commit=False,  # Save below to avoid logging
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
    case_blocks = []
    for i in range(num_cases):
        case_blocks.append(get_case_block(geo_property))
        if not i % CASE_BLOCK_CHUNK_SIZE:
            submit_chunk(domain, case_blocks)
            case_blocks = []
    if case_blocks:
        submit_chunk(domain, case_blocks)


def get_case_block(geo_property):
    fake = Faker()
    random_point = random_point_in_scotland()
    return CaseBlock(
        case_id=uuid4().hex,
        case_type=CASE_TYPE,
        case_name=fake.name(),
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
