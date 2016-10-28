import uuid
from StringIO import StringIO

from django.test import TestCase
from django.test.utils import override_settings

from casexml.apps.case.mock import CaseFactory
from corehq.apps.dump_reload.sql import dump_sql_data
from corehq.apps.dump_reload.sql import load_sql_data
from corehq.apps.dump_reload.sql.dump import get_model_domain_filter
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.models import XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL
from corehq.form_processor.tests.utils import FormProcessorTestUtils, create_form_for_test


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestSQLDumpLoad(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestSQLDumpLoad, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.factory = CaseFactory(domain=cls.domain)
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        super(TestSQLDumpLoad, cls).tearDownClass()

    @override_settings(ALLOW_FORM_PROCESSING_QUERIES=True)
    def _dump_and_load(self, expected_object_count, models):
        output_stream = StringIO()
        dump_sql_data(self.domain, [], output_stream)

        for model in models:
            filter = get_model_domain_filter(model, self.domain)
            model.objects.filter(filter).delete()

        dump_output = output_stream.getvalue()
        dump_lines = [line.strip() for line in dump_output.split('\n') if line.strip()]
        total_object_count, loaded_object_count = load_sql_data(dump_lines)

        self.assertEqual(expected_object_count, len(dump_lines))
        self.assertEqual(expected_object_count, loaded_object_count)
        self.assertEqual(expected_object_count, total_object_count)

        return dump_lines

    def test_dump_laod_form(self):
        pre_forms = [
            create_form_for_test(self.domain),
            create_form_for_test(self.domain)
        ]
        self._dump_and_load(4, [XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL])

        form_ids = FormAccessors(self.domain).get_all_form_ids_in_domain('XFormInstance')
        self.assertEqual(set(form_ids), set(form.form_id for form in pre_forms))

        for pre_form in pre_forms:
            post_form = FormAccessors(self.domain).get_form(pre_form.form_id)
            self.assertDictEqual(pre_form.to_json(), post_form.to_json())
