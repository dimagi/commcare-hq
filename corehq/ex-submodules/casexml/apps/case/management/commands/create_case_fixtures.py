# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import random
import uuid

import faker
import six
from django.core.management.base import BaseCommand
from six.moves import range

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.data_dictionary.util import add_properties_to_data_dictionary
from corehq.util.log import with_progress_bar


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
        structures = []
        for n in with_progress_bar(range(num_root_items)):
            owner = random.choice(owner_ids)
            # use a random locale for every 3 cases, otherwise use english
            # remove hu_HU because: https://github.com/joke2k/faker/pull/756
            locale = (random.choice(list(faker.config.AVAILABLE_LOCALES - set(['hu_HU'])))
                      if n % 3 == 0 else 'en_US')
            structures.extend(self._create_case_structure(locale, owner))
            if len(structures) >= 50:
                num_cases += len(CaseFactory(domain).create_or_update_cases(structures, user_id=owner))
                structures = []
        num_cases += len(CaseFactory(domain).create_or_update_cases(structures, user_id=owner))

        print("Created: {} cases".format(num_cases))

        self._generate_data_dictionary(domain)
        print("Generated data dictionary")

        if(self._generate_sample_app(domain)):
            print ("Generated Sample App")

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
            profile['favorite_color'] = getattr(fake, 'safe_color_name', fake.word)()
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

        licence_plate = fake.license_plate()
        car = CaseStructure(
            case_id=str(uuid.uuid4()),
            walk_related=False,
            attrs={
                "create": True,
                "case_type": "car",
                "owner_id": owner_id,
                "update": {
                    "name": fake.word(),
                    "licence_plate": licence_plate[0] if isinstance(licence_plate, tuple) else licence_plate,
                    "color": getattr(fake, 'safe_color_name', fake.word)(),
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

    def _generate_data_dictionary(self, domain):
        dictionary = {
            'adult': ['name', 'address', 'birthdate', 'blood_group', 'company', 'job', 'sex', 'lang'],
            'child': ['name', 'address', 'birthdate', 'blood_group', 'sex', 'age', 'favorite_color',
                      'favorite_number', 'lang'],
            'car': ['name', 'licence_plate', 'color'],
            'maintenance_record': ['name', 'date_performed', 'notes'],
        }
        for case_type, props in six.iteritems(dictionary):
            add_properties_to_data_dictionary(domain, case_type, props)

    def _generate_sample_app(self, domain):
        name = 'Case Fixtures App'
        for app in get_apps_in_domain(domain):
            if app.name == name:
                return False

        factory = AppFactory(domain, name)
        factory.app.comment = "App auto generated with ./manage.py create_case_fixtures"
        adult, adult_form = factory.new_basic_module('adult', 'adult')
        child, child_form = factory.new_basic_module('child', 'child')
        factory.form_opens_case(child_form, 'child', is_subcase=True, parent_tag='parent')
        car, car_form = factory.new_basic_module('car', 'car')
        factory.form_opens_case(car_form, 'car', is_subcase=True, parent_tag='car')
        maintenance_record, maintenance_record_form = factory.new_basic_module(
            'maintenance_record', 'maintenance_record')
        factory.form_opens_case(maintenance_record_form, 'maintenance_record',
                                is_subcase=True, parent_tag='maintenance_record_of_car',
                                is_extension=True)

        factory.app.save()
        return True
