from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    FormExportInstance,
    CaseExportInstance,
)
from corehq.apps.export.dbaccessors import (
    get_latest_case_export_schema,
    get_latest_form_export_schema,
    get_form_export_instances,
    get_case_export_instances,
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
        cls.form_schema_other = FormExportDataSchema(
            domain='other',
            app_id=cls.app_id,
            xmlns=cls.xmlns,
        )
        cls.form_schema_before = FormExportDataSchema(
            domain=cls.domain,
            app_id=cls.app_id,
            xmlns=cls.xmlns,
            created_on=datetime.utcnow() - timedelta(1)
        )

        cls.case_schema = CaseExportDataSchema(
            domain=cls.domain,
            case_type=cls.case_type,
        )

        cls.case_schema_other = CaseExportDataSchema(
            domain=cls.domain,
            case_type='other',
        )
        cls.case_schema_before = FormExportDataSchema(
            domain=cls.domain,
            case_type=cls.case_type,
            created_on=datetime.utcnow() - timedelta(1)
        )

        cls.schemas = [
            cls.form_schema,
            cls.form_schema_before,
            cls.form_schema_other,
            cls.case_schema_before,
            cls.case_schema,
            cls.case_schema_other,
        ]
        for schema in cls.schemas:
            schema.save()

    @classmethod
    def tearDownClass(cls):
        for schema in cls.schemas:
            schema.delete()

    def test_get_latest_form_export_schema(self):
        schema = get_latest_form_export_schema(self.domain, self.app_id, self.xmlns)

        self.assertEqual(schema._id, self.form_schema._id)

    def test_get_latest_form_export_schema_empty(self):
        schema = get_latest_form_export_schema(self.domain, self.app_id, 'not-found')

        self.assertEqual(schema, None)

    def test_get_latest_case_export_schema(self):
        schema = get_latest_case_export_schema(self.domain, self.case_type)

        self.assertEqual(schema._id, self.case_schema._id)

    def test_get_latest_case_export_schema_empty(self):
        schema = get_latest_case_export_schema(self.domain, 'not-found')

        self.assertEqual(schema, None)


class TestExportInstanceDBAccessors(TestCase):
    dependent_apps = ['corehq.apps.export', 'corehq.couchapps']

    domain = 'my-domain'

    @classmethod
    def setUpClass(cls):
        cls.form_instance_deid = FormExportInstance(
            domain=cls.domain,
            name='Forms',
            is_deidentified=True
        )
        cls.form_instance_wrong = FormExportInstance(
            domain='wrong-domain',
            name='Forms',
        )
        cls.case_instance_deid = CaseExportInstance(
            domain=cls.domain,
            name='Cases',
            is_deidentified=True
        )
        cls.case_instance = CaseExportInstance(
            domain=cls.domain,
            name='Cases',
            is_deidentified=False
        )
        cls.instances = [
            cls.form_instance_deid,
            cls.form_instance_wrong,
            cls.case_instance,
            cls.case_instance_deid,
        ]
        for instance in cls.instances:
            instance.save()

    @classmethod
    def tearDownClass(cls):
        for instance in cls.instances:
            instance.delete()

    def test_get_form_export_instances(self):
        instances = get_form_export_instances(self.domain)
        self.assertEqual(len(instances), 1)

    def test_get_case_export_instances(self):
        instances = get_case_export_instances(self.domain)
        self.assertEqual(len(instances), 2)

    def test_get_case_export_instances_wrong_domain(self):
        instances = get_case_export_instances('wrong')
        self.assertEqual(len(instances), 0)
