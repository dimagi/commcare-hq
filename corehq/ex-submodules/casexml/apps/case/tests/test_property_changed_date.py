from datetime import datetime
import pytz

from django.test import TestCase
from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.util import get_date_case_property_changed
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class TestDateCasePropertyChanged(TestCase):
    def setUp(self):
        self.factory = CaseFactory('domain')
        self.case = self.factory.create_case()

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
            get_date_case_property_changed(case, "abc", "updated")
        )
