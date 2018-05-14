# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import random
import uuid

import faker
from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure


class Command(BaseCommand):
    help = "Creates a corpus of test cases with reasonable relationships"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('num_root_items', type=int, help="The number of parent cases to create")
        parser.add_argument(
            'owner_ids',
            help=("The owners these cases should be assigned to."
                  "The cases will be randomly spread amongst these owners"),
            nargs="+"
        )

    def handle(self, domain, num_root_items, owner_ids, **kwargs):
        num_cases = 0
        for n in range(num_root_items):
            owner = random.choice(owner_ids)
            # use a random locale for every 3 cases, otherwise use english
            locale = random.choice(list(faker.config.AVAILABLE_LOCALES)) if n % 3 == 0 else 'en_US'
            structures = self._create_case_structure(locale, owner)
            num_cases += len(CaseFactory(domain).create_or_update_cases(structures, user_id=owner))

        print("Created: {} cases".format(num_cases))

    def _create_case_structure(self, locale, owner_id):
        fake = faker.Faker(locale)
        structures = []
        profile = fake.profile(fields=[
            'name', 'address', 'birthdate', 'blood_group', 'company', 'job', 'sex'
        ])
        profile['lang'] = locale
        adult = CaseStructure(
            case_id=str(uuid.uuid4()),
            attrs={
                "create": True,
                "case_type": "adult",
                "owner_id": owner_id,
                "update": profile,
            },
        )
        structures.append(adult)
        for _ in range(random.randint(1, 5)):
            profile = fake.profile(fields=['name', 'address', 'birthdate', 'blood_group', 'sex'])
            profile['age'] = fake.random_int(1, 15)
            profile['favorite_color'] = fake.safe_color_name()
            profile['favorite_number'] = fake.random_int(1, 1000)
            profile['lang'] = locale
            child = CaseStructure(
                case_id=str(uuid.uuid4()),
                walk_related=False,
                attrs={
                    "create": True,
                    "case_type": "child",
                    "owner_id": owner_id,
                    "update": profile,
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=adult.case_id, attrs={"create": False}),
                    identifier='parent',
                    relationship='child',
                    related_type='adult',
                )]
            )
            structures.append(child)

        car = CaseStructure(
            case_id=str(uuid.uuid4()),
            walk_related=False,
            attrs={
                "create": True,
                "case_type": "car",
                "owner_id": owner_id,
                "update": {
                    "name": fake.word(),
                    "licence_plate": fake.license_plate(),
                    "color": fake.safe_color_name(),
                },
            },
            indices=[CaseIndex(
                CaseStructure(case_id=adult.case_id, attrs={"create": False}),
                identifier='car',
                relationship='child',
                related_type='adult',
            )]
        )
        structures.append(car)

        for _ in range(random.randint(1, 3)):
            maintenance_record = CaseStructure(
                case_id=str(uuid.uuid4()),
                walk_related=False,
                attrs={
                    "create": True,
                    "case_type": "maintenance_record",
                    "owner_id": '-',
                    "update": {
                        "name": fake.word(),
                        "date_performed": fake.date(pattern="%Y-%m-%d"),
                        "notes": fake.sentence(),
                    },
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=car.case_id, attrs={"create": False}),
                    identifier='maintenance_record_of_car',
                    relationship='extension',
                    related_type='car',
                )]
            )
            structures.append(maintenance_record)
        return structures
