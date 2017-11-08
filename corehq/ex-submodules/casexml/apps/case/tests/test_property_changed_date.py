from __future__ import absolute_import
from datetime import datetime
import pytz

from django.test import TestCase
from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_xforms, delete_all_cases
from casexml.apps.case.util import get_datetime_case_property_changed
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class TestDateCasePropertyChanged(TestCase):
    def setUp(self):
        self.factory = CaseFactory('domain')
        self.case = self.factory.create_case()
        self.other_case = self.factory.create_case()

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()

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
