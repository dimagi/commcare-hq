import uuid
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms

from corehq.apps.domain.models import Domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqadmin.management.commands.stale_data_in_es import DataRow
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.document_stores import (
    CaseDocumentStore,
    FormDocumentStore,
)
from corehq.form_processor.utils.xform import (
    FormSubmissionBuilder,
    TestFormMetadata,
)


class ExitEarlyException(Exception):
    pass


@es_test(requires=[case_search_adapter, case_adapter, form_adapter], setup_class=True)
class TestStaleDataInESSQL(TestCase):

    project_name = 'sql-project'
    case_type = 'patient'
    form_xmlns = None

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

    def test_case_missing_date(self):
        self._test_case_missing_date()

    def test_case_resume(self):
        iteration_key = uuid.uuid4().hex

        def _make_fake_es_check(num_to_process):
            seen = []

            def _fake_es_check(chunk):
                chunk = list(chunk)
                if len(seen) == num_to_process:
                    raise ExitEarlyException(seen)
                seen.extend(chunk)
                for case_id, case_type, modified_on, domain in chunk:
                    yield DataRow(
                        doc_id=case_id, doc_type='CommCareCase', doc_subtype=case_type, domain=domain,
                        es_date=None, primary_date=modified_on
                    )

            return _fake_es_check

        def call(num_to_process=None, expect_exception=None):
            _fake_es_check = _make_fake_es_check(num_to_process)
            patch_path = 'corehq.apps.hqadmin.management.commands.stale_data_in_es'
            with mock.patch(f'{patch_path}.CHUNK_SIZE', 1),\
                    mock.patch(f'{patch_path}.CaseHelper._yield_missing_in_es', _fake_es_check):
                return self._stale_data_in_es(
                    'case', iteration_key=iteration_key, expect_exception=expect_exception
                )

        form, cases = self._submit_form(self.project.name, new_cases=4)

        # process first 2 then raise exception
        self._assert_not_in_sync(call(2, expect_exception=ExitEarlyException), rows=[
            (case.case_id, 'CommCareCase', case.type, case.domain, None, case.server_modified_on)
            for case in cases[:2]
        ])

        # process rest - should start at 3rd doc
        self._assert_not_in_sync(call(4), rows=[
            (case.case_id, 'CommCareCase', case.type, case.domain, None, case.server_modified_on)
            for case in cases[2:]
        ])

    def test_form_resume(self):
        iteration_key = uuid.uuid4().hex

        def _make_fake_es_check(num_to_process):
            seen = []

            def _fake_es_check(chunk):
                chunk = list(chunk)
                if len(seen) == num_to_process:
                    raise ExitEarlyException(seen)
                seen.extend(chunk)
                for form_id, doc_type, xmlns, modified_on, domain in chunk:
                    yield DataRow(
                        doc_id=form_id, doc_type=doc_type, doc_subtype=xmlns, domain=domain,
                        es_date=None, primary_date=modified_on
                    )

            return _fake_es_check

        def call(num_to_process=None, expect_exception=None):
            _fake_es_check = _make_fake_es_check(num_to_process)
            patch_path = 'corehq.apps.hqadmin.management.commands.stale_data_in_es'
            with mock.patch(f'{patch_path}.CHUNK_SIZE', 1), \
                    mock.patch(f'{patch_path}.FormHelper._yield_missing_in_es', _fake_es_check):
                return self._stale_data_in_es(
                    'form', iteration_key=iteration_key, expect_exception=expect_exception
                )

        forms = [
            self._submit_form(self.project.name)[0] for i in range(4)
        ]

        # process first 2 then raise exception
        self._assert_not_in_sync(call(2, expect_exception=ExitEarlyException), rows=[
            (form.form_id, 'XFormInstance', form.xmlns, form.domain, None, form.received_on)
            for form in forms[:2]
        ])

        # process rest - should start at 3rd doc
        self._assert_not_in_sync(call(4), rows=[
            (form.form_id, 'XFormInstance', form.xmlns, form.domain, None, form.received_on)
            for form in forms[2:]
        ])

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

    def _test_case_missing_date(self):
        def call():
            return self._stale_data_in_es('case')
        form, (case,) = self._submit_form(self.project.name, new_cases=1)

        pg_modified_on = case.server_modified_on
        case.server_modified_on = None
        self._send_cases_to_es([case], refetch_doc=False)
        case.server_modified_on = pg_modified_on

        self._assert_not_in_sync(call(), rows=[
            (case.case_id, 'CommCareCase', case.type, case.domain, None, case.server_modified_on)
        ])

    def _stale_data_in_es(self, *args, **kwargs):
        f = StringIO()
        expect_exception = kwargs.pop('expect_exception', None)
        with mock.patch('sys.stdout', f), mock.patch('sys.stderr', StringIO()):
            if expect_exception:
                with self.assertRaises(expect_exception):
                    call_command('stale_data_in_es', *args, stdout=f, **kwargs)
            else:
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

        form_xml = FormSubmissionBuilder(
            form_id=str(uuid.uuid4()),
            case_blocks=case_blocks,
            metadata=TestFormMetadata(xmlns=self.form_xmlns) if self.form_xmlns else None
        ).as_xml_string()
        result = submit_form_locally(form_xml, domain)
        return result.xform, result.cases

    def _send_forms_to_es(self, forms):
        form_adapter.bulk_index(
            [FormDocumentStore(form.domain, form.xmlns).get_document(form.form_id) for form in forms],
            refresh=True
        )

        self.forms_to_delete_from_es.update(form.form_id for form in forms)

    def _send_cases_to_es(self, cases, refetch_doc=True):
        es_cases = []
        for case in cases:
            if refetch_doc:
                es_cases.append(CaseDocumentStore(case.domain, case.type).get_document(case.case_id))
            else:
                es_cases.append(case)
        case_adapter.bulk_index(es_cases, refresh=True)
        case_search_adapter.bulk_index(cases, refresh=True)

        self.cases_to_delete_from_es.update(case.case_id for case in cases)

    @classmethod
    def _delete_forms_from_es(cls, form_ids):
        form_adapter.bulk_delete(form_ids, refresh=True)

    @classmethod
    def _delete_cases_from_es(cls, case_ids):
        case_adapter.bulk_delete(case_ids, refresh=True)

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
        delete_all_cases()
        cls.project = Domain.get_or_create_with_name(cls.project_name, is_active=True)
        cls.project.save()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()

    def setUp(self):
        self.forms_to_delete_from_es = set()
        self.cases_to_delete_from_es = set()

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        self._delete_forms_from_es(self.forms_to_delete_from_es)
        self._delete_cases_from_es(self.cases_to_delete_from_es)
