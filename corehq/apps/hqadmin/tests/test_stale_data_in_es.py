import uuid
from io import StringIO
from unittest import skip

from django.core.management import call_command
from django.test import TestCase
from django.utils.decorators import method_decorator

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.document_stores import FormDocumentStore, CaseDocumentStore
from corehq.form_processor.utils.xform import FormSubmissionBuilder
from corehq.pillows.case import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.elastic import reset_es_index


class TestStaleDataInESSQL(TestCase):

    use_sql_backend = True
    case_type = 'patient'

    def test_no_output(self):
        self._assert_in_sync(self._stale_data_in_es('form'))
        self._assert_in_sync(self._stale_data_in_es('case'))
        self._assert_in_sync(self._stale_data_in_es('form', 'case'))

    def test_form_missing_then_not(self):
        self._test_form_missing_then_not({})

    def test_form_missing_then_not_domain_specific(self):
        self._test_form_missing_then_not({'domain': self.project.name})

    def test_case_missing_then_not(self):
        self._test_case_missing_then_not({})

    def test_case_missing_then_not_domain_specific(self):
        self._test_case_missing_then_not({'domain': self.project.name})

    def _test_form_missing_then_not(self, cmd_kwargs):
        def call():
            return self._stale_data_in_es('form', **cmd_kwargs)

        form, cases = self._submit_form(self.project.name)
        self._assert_not_in_sync(call(), rows=[
            (form.form_id, 'XFormInstance', form.xmlns, form.domain, None, form.received_on)
        ])

        self._send_forms_to_es([form])
        self._assert_in_sync(call())

        form.archive(trigger_signals=False)
        self._assert_not_in_sync(call(), rows=[
            (form.form_id, 'XFormArchived', form.xmlns, form.domain, form.received_on, form.received_on)
        ])

        self._send_forms_to_es([form])
        self._assert_in_sync(call())

        form.unarchive(trigger_signals=False)
        self._assert_not_in_sync(call(), rows=[
            (form.form_id, 'XFormInstance', form.xmlns, form.domain, form.received_on, form.received_on)
        ])

        self._send_forms_to_es([form])
        self._assert_in_sync(call())

    def _test_case_missing_then_not(self, cmd_kwargs):
        def call():
            return self._stale_data_in_es('case', **cmd_kwargs)
        form, (case,) = self._submit_form(self.project.name, new_cases=1)
        self._assert_not_in_sync(call(), rows=[
            (case.case_id, 'CommCareCase', case.type, case.domain, None, case.server_modified_on)
        ])

        self._send_cases_to_es([case])
        self._assert_in_sync(call())

        old_date = case.server_modified_on
        form, (case,) = self._submit_form(self.project.name, update_cases=[case])
        self._assert_not_in_sync(call(), rows=[
            (case.case_id, 'CommCareCase', case.type, case.domain, old_date, case.server_modified_on)
        ])

        self._send_cases_to_es([case])
        self._assert_in_sync(call())

    @staticmethod
    def _stale_data_in_es(*args, **kwargs):
        f = StringIO()
        call_command('stale_data_in_es', *args, stdout=f, **kwargs)
        return f.getvalue()

    def _submit_form(self, domain, new_cases=0, update_cases=()):
        case_blocks = [
            CaseBlock(
                case_id=str(uuid.uuid4()),
                case_type=self.case_type,
                create={'name': str(uuid.uuid4())[:5]},
            )
            for i in range(new_cases)
        ]
        case_blocks += [
            CaseBlock(
                case_id=case.case_id,
                update={}
            )
            for case in update_cases
        ]

        form_xml = FormSubmissionBuilder(form_id=str(uuid.uuid4()), case_blocks=case_blocks).as_xml_string()
        result = submit_form_locally(form_xml, domain)
        return result.xform, result.cases

    @classmethod
    def _send_forms_to_es(cls, forms):
        for form in forms:

            es_form = transform_xform_for_elasticsearch(
                FormDocumentStore(form.domain, form.xmlns).get_document(form.form_id)
            )
            send_to_elasticsearch('forms', es_form)

        cls.elasticsearch.indices.refresh(XFORM_INDEX_INFO.index)

    @classmethod
    def _send_cases_to_es(cls, cases):
        for case in cases:
            es_case = transform_case_for_elasticsearch(
                CaseDocumentStore(case.domain, case.type).get_document(case.case_id)
            )
            send_to_elasticsearch('cases', es_case)

        cls.elasticsearch.indices.refresh(CASE_INDEX_INFO.index)

    def _assert_in_sync(self, output):
        self.assertEqual(
            output,
            'Doc ID\tDoc Type\tDoc Subtype\tDomain\tES Date\tCorrect Date\n'
        )

    def _assert_not_in_sync(self, output, rows):
        content = "".join('{}\n'.format('\t'.join(map(str, row))) for row in rows)
        self.assertEqual(
            output,
            f'Doc ID\tDoc Type\tDoc Subtype\tDomain\tES Date\tCorrect Date\n{content}'
        )

    @classmethod
    def setUpClass(cls):
        cls.project = Domain.get_or_create_with_name(
            'project', is_active=True, use_sql_backend=cls.use_sql_backend)
        cls.project.save()
        cls.elasticsearch = get_es_new()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        reset_es_index(XFORM_INDEX_INFO)
        reset_es_index(CASE_INDEX_INFO)


@method_decorator(skip("Not yet implemented"), 'test_form_missing_then_not')
@method_decorator(skip("Not yet implemented"), 'test_form_missing_then_not_domain_specific')
@method_decorator(skip("Not yet implemented"), 'test_case_missing_then_not')
class TestStaleDataInESCouch(TestStaleDataInESSQL):

    use_sql_backend = False
    case_type = 'COUCH_TYPE_NOT_SUPPORTED'
