import uuid
from StringIO import StringIO

from django.test import TestCase
from django.test.utils import override_settings

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.dump_reload.sql import dump_sql_data
from corehq.apps.dump_reload.sql import load_sql_data
from corehq.apps.dump_reload.sql.dump import get_model_domain_filter
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.models import (
    XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL,
    CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction
)
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
        cls.form_accessors = FormAccessors(cls.domain)
        cls.case_accessors = CaseAccessors(cls.domain)

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
            self.assertFalse(model.objects.all().exists())

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
        expected_object_count = 4  # 2 forms, 2 form attachments
        self._dump_and_load(expected_object_count, [XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL])

        form_ids = self.form_accessors.get_all_form_ids_in_domain('XFormInstance')
        self.assertEqual(set(form_ids), set(form.form_id for form in pre_forms))

        for pre_form in pre_forms:
            post_form = self.form_accessors.get_form(pre_form.form_id)
            self.assertDictEqual(pre_form.to_json(), post_form.to_json())

    def test_sql_dump_load_case(self):
        pre_cases = self.factory.create_or_update_case(
            CaseStructure(
                attrs={'case_name': 'child', 'update': {'age': 3, 'diabetic': False}},
                indices=[
                    CaseIndex(CaseStructure(attrs={'case_name': 'parent', 'update': {'age': 42}})),
                ]
            )
        )
        pre_cases[0] = self.factory.create_or_update_case(CaseStructure(
            case_id=pre_cases[0].case_id,
            attrs={'external_id': 'billie jean', 'update': {'name': 'Billie Jean'}}
        ))[0]

        object_count = 10  # 2 forms, 2 form attachment, 2 cases, 3 case transactions, 1 case index
        self._dump_and_load(object_count, [
            XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL,
            CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction
        ])

        case_ids = self.case_accessors.get_case_ids_in_domain()
        self.assertEqual(set(case_ids), set(case.case_id for case in pre_cases))
        for pre_case in pre_cases:
            post_case = self.case_accessors.get_case(pre_case.case_id)
            self.assertDictEqual(pre_case.to_json(), post_case.to_json())
