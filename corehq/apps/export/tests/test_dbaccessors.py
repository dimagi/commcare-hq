from django.test import TestCase

from corehq.apps.export.models import FormExportDataSchema, CaseExportDataSchema
from corehq.apps.export.dbaccessors import (
    get_latest_case_export_schema_id,
    get_latest_form_export_schema_id,
)


class TestExportDBAccessors(TestCase):
    dependent_apps = ['corehq.apps.export', 'corehq.couchapps']
    domain = 'my-domain'
    app_id = '1234'
    xmlns = 'http://openthatrose.com'
    case_type = 'candy'

    @classmethod
    def setUpClass(cls):
        cls.form_schema = FormExportDataSchema(
            domain=cls.domain,
            app_id=cls.app_id,
            xmlns=cls.xmlns,
        )
        cls.form_schema_decoy = FormExportDataSchema(
            domain='decoy',
            app_id=cls.app_id,
            xmlns=cls.xmlns,
        )

        cls.case_schema = CaseExportDataSchema(
            domain=cls.domain,
            case_type=cls.case_type,
        )

        cls.case_schema_decoy = CaseExportDataSchema(
            domain=cls.domain,
            case_type='decoy',
        )

        cls.schemas = [
            cls.form_schema,
            cls.form_schema_decoy,
            cls.case_schema,
            cls.case_schema_decoy,
        ]
        for schema in cls.schemas:
            schema.save()

    @classmethod
    def tearDownClass(cls):
        for schema in cls.schemas:
            schema.delete()

    def test_get_latest_form_export_schema_id(self):
        schema_id = get_latest_form_export_schema_id(self.domain, self.app_id, self.xmlns)

        self.assertEqual(schema_id, self.form_schema._id)

    def test_get_latest_form_export_schema_id_empty(self):
        schema_id = get_latest_form_export_schema_id(self.domain, self.app_id, 'not-found')

        self.assertEqual(schema_id, None)

    def test_get_latest_case_export_schema_id(self):
        schema_id = get_latest_case_export_schema_id(self.domain, self.case_type)

        self.assertEqual(schema_id, self.case_schema._id)

    def test_get_latest_case_export_schema_id_empty(self):
        schema_id = get_latest_case_export_schema_id(self.domain, 'not-found')

        self.assertEqual(schema_id, None)
