from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    FormExportInstance,
    CaseExportInstance,
    CaseInferredSchema,
    FormInferredSchema,
)
from corehq.apps.export.dbaccessors import (
    get_latest_case_export_schema,
    get_latest_form_export_schema,
    get_form_export_instances,
    get_case_export_instances,
    get_export_count_by_domain,
    get_deid_export_count,
    get_daily_saved_export_ids_for_auto_rebuild,
    get_properly_wrapped_export_instance,
    get_case_inferred_schema,
    get_form_inferred_schema,
    get_form_exports_by_domain,
    get_case_exports_by_domain
)


class TestExportDBAccessors(TestCase):
    domain = 'my-domain'
    app_id = '1234'
    xmlns = 'http://openthatrose.com'
    case_type = 'candy'

    @classmethod
    def setUpClass(cls):
        super(TestExportDBAccessors, cls).setUpClass()
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
        cls.case_schema_before = CaseExportDataSchema(
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
        super(TestExportDBAccessors, cls).tearDownClass()

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

    domain = 'my-domain'

    @classmethod
    def setUpClass(cls):
        super(TestExportInstanceDBAccessors, cls).setUpClass()
        cls.form_instance = FormExportInstance(
            domain=cls.domain,
            name='Forms',
            is_deidentified=False
        )
        cls.form_instance_deid = FormExportInstance(
            domain=cls.domain,
            name='Forms',
            is_deidentified=True
        )
        cls.form_instance_wrong = FormExportInstance(
            domain='wrong-domain',
            name='Forms',
        )
        cls.form_instance_daily_saved = FormExportInstance(
            domain='wrong-domain',
            is_daily_saved_export=True,
            auto_rebuild_enabled=True,
            last_accessed=datetime.utcnow()
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
        cls.case_instance_daily_saved = CaseExportInstance(
            domain='wrong-domain',
            is_daily_saved_export=True,
            auto_rebuild_enabled=True,
            last_accessed=(datetime.utcnow() - timedelta(days=4))
        )

        cls.instances = [
            cls.form_instance,
            cls.form_instance_deid,
            cls.form_instance_wrong,
            cls.form_instance_daily_saved,
            cls.case_instance,
            cls.case_instance_deid,
            cls.case_instance_daily_saved,
        ]
        for instance in cls.instances:
            instance.save()

    @classmethod
    def tearDownClass(cls):
        for instance in cls.instances:
            instance.delete()
        super(TestExportInstanceDBAccessors, cls).tearDownClass()

    def test_get_form_export_instances(self):
        instances = get_form_export_instances(self.domain)
        self.assertEqual(len(instances), 2)

    def test_get_case_export_instances(self):
        instances = get_case_export_instances(self.domain)
        self.assertEqual(len(instances), 2)

    def test_get_count_export_instances(self):
        self.assertEqual(
            get_export_count_by_domain(self.domain),
            4
        )

    def test_get_count_deid_export_instances(self):
        self.assertEqual(
            get_deid_export_count(self.domain),
            2
        )

    def test_get_case_export_instances_wrong_domain(self):
        instances = get_case_export_instances('wrong')
        self.assertEqual(len(instances), 0)

    def test_get_daily_saved_exports(self):
        recently_accessed_instance_ids = get_daily_saved_export_ids_for_auto_rebuild(
            datetime.utcnow() - timedelta(days=2))
        self.assertEqual(
            set(recently_accessed_instance_ids),
            {self.form_instance_daily_saved._id}
        )

    def test_get_properly_wrapped_export_instance(self):
        instance = get_properly_wrapped_export_instance(self.form_instance_daily_saved._id)
        self.assertEqual(type(instance), type(self.form_instance_daily_saved))

        instance = get_properly_wrapped_export_instance(self.case_instance._id)
        self.assertEqual(type(instance), type(self.case_instance))

    def test_deid_form_exports_permissions(self):
        instances = get_form_exports_by_domain(self.domain, has_deid_permissions=True)
        self.assertEqual(len(instances), 2)

        instances = get_form_exports_by_domain(self.domain, has_deid_permissions=False)
        self.assertEqual(len(instances), 1)

    def test_deid_case_exports_permissions(self):
        instances = get_case_exports_by_domain(self.domain, has_deid_permissions=True)
        self.assertEqual(len(instances), 2)

        instances = get_case_exports_by_domain(self.domain, has_deid_permissions=False)
        self.assertEqual(len(instances), 1)


class TestInferredSchemasDBAccessors(TestCase):

    domain = 'inferred-domain'
    case_type = 'inferred'
    xmlns = 'inferred'
    app_id = 'inferred'

    @classmethod
    def setUpClass(cls):
        super(TestInferredSchemasDBAccessors, cls).setUpClass()
        cls.inferred_schema = CaseInferredSchema(
            domain=cls.domain,
            case_type=cls.case_type,
        )
        cls.inferred_schema_other = CaseInferredSchema(
            domain=cls.domain,
            case_type='other',
        )
        cls.form_inferred_schema_other = FormInferredSchema(
            domain=cls.domain,
            xmlns='other',
            app_id='other',
        )
        cls.form_inferred_schema = FormInferredSchema(
            domain=cls.domain,
            xmlns=cls.xmlns,
            app_id=cls.app_id,
        )

        cls.schemas = [
            cls.inferred_schema,
            cls.inferred_schema_other,
            cls.form_inferred_schema,
            cls.form_inferred_schema_other,
        ]
        for schema in cls.schemas:
            schema.save()

    @classmethod
    def tearDownClass(cls):
        for schema in cls.schemas:
            schema.delete()
        super(TestInferredSchemasDBAccessors, cls).tearDownClass()

    def test_get_case_inferred_schema(self):
        result = get_case_inferred_schema(self.domain, self.case_type)
        self.assertIsNotNone(result)
        self.assertEqual(result._id, self.inferred_schema._id)

    def test_get_case_inferred_schema_missing(self):
        result = get_case_inferred_schema(self.domain, 'not-here')
        self.assertIsNone(result)

    def test_get_form_inferred_schema(self):
        result = get_form_inferred_schema(self.domain, self.app_id, self.xmlns)
        self.assertIsNotNone(result)
        self.assertEqual(result._id, self.form_inferred_schema._id)

    def test_get_form_inferred_schema_missing(self):
        result = get_form_inferred_schema(self.domain, 'not-here', self.xmlns)
        self.assertIsNone(result)
