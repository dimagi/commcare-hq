from __future__ import absolute_import

from __future__ import unicode_literals
from datetime import datetime

import pytz
from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from casexml.apps.case.util import (
    get_all_changes_to_case_property,
    get_datetime_case_property_changed,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends


class TestCasePropertyChanged(TestCase):
    def setUp(self):
        self.factory = CaseFactory('domain')
        self.case = self.factory.create_case(owner_id='owner')
        self.other_case = self.factory.create_case()

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()

    @run_with_all_backends
    def test_date_case_property_changed(self):
        updated_on = datetime(2015, 5, 3, 12, 11)
        # submit 2 updates
        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'abc': "updated"
                    },
                    "date_modified": updated_on
                }),
        )
        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'bcd': "updated"
                    },
                }),
        )
        case = CaseAccessors('domain').get_case(self.case.case_id)

        self.assertEqual(
            updated_on.replace(tzinfo=pytz.UTC),
            get_datetime_case_property_changed(case, "abc", "updated")
        )

    @run_with_all_backends
    def test_multiple_cases_in_update(self):
        day_1 = datetime(2015, 5, 1, 12, 11)
        day_2 = datetime(2015, 5, 2, 12, 11)

        # Submit two updates TOGETHER, one for this case, but irrelevant,
        # and one for another case, but touching the same property
        self.factory.create_or_update_cases([
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'not_relevant': "updated"
                    },
                    "date_modified": day_1,
                }),
            CaseStructure(
                self.other_case.case_id,
                attrs={
                    "update": {
                        'relevant_property': "updated"
                    },
                    "date_modified": day_1,
                }),
        ])

        # Submit an update that DOES modify the relevant property
        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'relevant_property': "updated"
                    },
                    "date_modified": day_2,
                }),
        )
        case = CaseAccessors('domain').get_case(self.case.case_id)

        self.assertEqual(
            day_2.replace(tzinfo=pytz.UTC),
            get_datetime_case_property_changed(case, "relevant_property", "updated")
        )

    @run_with_all_backends
    def test_owner_id_changed(self):
        changes = get_all_changes_to_case_property(self.case, 'owner_id')
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].new_value, 'owner')

        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'owner_id': 'new_owner'
                    },
                }),
        )
        case = CaseAccessors('domain').get_case(self.case.case_id)

        changes = get_all_changes_to_case_property(case, 'owner_id')
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0].new_value, 'owner')
        self.assertEqual(changes[1].new_value, 'new_owner')
