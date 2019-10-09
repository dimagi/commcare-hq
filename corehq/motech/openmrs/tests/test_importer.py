import datetime

from django.test import SimpleTestCase, TestCase

from mock import patch

from corehq.motech.openmrs.const import (
    IMPORT_FREQUENCY_DAILY,
    IMPORT_FREQUENCY_MONTHLY,
    IMPORT_FREQUENCY_WEEKLY,
)
from corehq.motech.openmrs.models import OpenmrsImporter

domain_name = 'test-domain'


class ImporterTests(SimpleTestCase):

    def test_import_daily(self):
        importer = OpenmrsImporter(
            domain=domain_name,
            import_frequency=IMPORT_FREQUENCY_DAILY,
        )
        self.assertTrue(importer.should_import_today())

    def test_import_weekly_tuesday(self):
        with patch('corehq.motech.openmrs.models.datetime') as datetime_mock:
            datetime_mock.today.return_value = datetime.date(2019, 9, 17)
            importer = OpenmrsImporter(
                domain=domain_name,
                import_frequency=IMPORT_FREQUENCY_WEEKLY,
            )
            self.assertTrue(importer.should_import_today())

    def test_import_weekly_not_tuesday(self):
        with patch('corehq.motech.openmrs.models.datetime') as datetime_mock:
            datetime_mock.today.return_value = datetime.date(2019, 9, 16)
            importer = OpenmrsImporter(
                domain=domain_name,
                import_frequency=IMPORT_FREQUENCY_WEEKLY,
            )
            self.assertFalse(importer.should_import_today())

    def test_import_monthly_first(self):
        with patch('corehq.motech.openmrs.models.datetime') as datetime_mock:
            datetime_mock.today.return_value = datetime.date(2019, 9, 1)
            importer = OpenmrsImporter(
                domain=domain_name,
                import_frequency=IMPORT_FREQUENCY_MONTHLY,
            )
            self.assertTrue(importer.should_import_today())

    def test_import_monthly_not_first(self):
        with patch('corehq.motech.openmrs.models.datetime') as datetime_mock:
            datetime_mock.today.return_value = datetime.date(2019, 9, 2)
            importer = OpenmrsImporter(
                domain=domain_name,
                import_frequency=IMPORT_FREQUENCY_MONTHLY,
            )
            self.assertFalse(importer.should_import_today())


class LocationTypeNameTest(TestCase):

    def test_wrapping_old_definition(self):
        imp = OpenmrsImporter.wrap({
            'domain': domain_name,
            'location_type_name': ''
        })
        try:
            imp.save()
        finally:
            imp.delete()
