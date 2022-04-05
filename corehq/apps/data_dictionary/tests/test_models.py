import datetime
import uuid

from django.test import TestCase

from corehq.apps.case_importer import exceptions
from corehq.apps.data_dictionary.models import CaseProperty, CasePropertyAllowedValue, CaseType
from corehq.apps.domain.shortcuts import create_domain


class TestCaseProperty(TestCase):
    domain_name = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.case_type = CaseType(name="caseType", domain=cls.domain_name)
        cls.case_type.save()
        cls.date_property = CaseProperty(case_type=cls.case_type, data_type="date", name="dob")
        cls.date_property.save()
        cls.valid_date = datetime.date.today().isoformat()
        cls.select_property = CaseProperty.objects.create(
            case_type=cls.case_type, data_type="select", name="status")
        cls.valid_choices = ["todo", "in-progress", "complete"]
        for choice in cls.valid_choices:
            CasePropertyAllowedValue.objects.create(case_property=cls.select_property, allowed_value=choice)

    @classmethod
    def tearDownClass(cls):
        cls.case_type.delete()
        cls.domain.delete()
        super().tearDownClass()

    def test_check_valid_date(self):
        # check_validity raises exception on invalid date so just
        # calling it and not getting an exception indicates validity
        self.date_property.check_validity(self.valid_date)

    def test_check_invalid_date(self):
        with self.assertRaises(exceptions.InvalidDate):
            self.date_property.check_validity("2022")
        with self.assertRaises(exceptions.InvalidDate):
            self.date_property.check_validity("2022-14-03")
        with self.assertRaises(exceptions.InvalidDate):
            self.date_property.check_validity(f"Embedded {self.valid_date} in a longer string")
        with self.assertRaises(exceptions.InvalidDate):
            # caller is responsible for stripping any surrounding whitespace
            self.date_property.check_validity(f"  {self.valid_date} ")

    def test_check_valid_selections(self):
        # Simply not raising an exception indicates it passes validity check
        for choice in self.valid_choices:
            self.select_property.check_validity(choice)

    def test_check_invalid_choice(self):
        # We require strict matching, including case. Uppercase a valid choice
        # and ensure it is not accepted.
        with self.assertRaises(exceptions.InvalidSelectValue):
            self.select_property.check_validity(self.valid_choices[0].upper())
