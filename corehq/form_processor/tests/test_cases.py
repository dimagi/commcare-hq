import uuid
from datetime import datetime

from django.conf import settings
from django.test import TestCase

from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import (
    CaseTransaction,
    CommCareCase,
    XFormInstance,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.sql_db.util import get_db_alias_for_partitioned_doc

DOMAIN = 'test-case-accessor'


@sharded
class CaseAccessorTestsSQL(TestCase):

    def tearDown(self):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
            FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)
        super(CaseAccessorTestsSQL, self).tearDown()

    def test_get_case_by_id(self):
        case = _create_case()
        with self.assertNumQueries(1, using=case.db):
            case = CommCareCase.objects.get_case(case.case_id)
        self.assertIsNotNone(case)
        self.assertIsInstance(case, CommCareCase)
        self.assertEqual(DOMAIN, case.domain)
        self.assertEqual('user1', case.owner_id)

    def test_get_case_with_empty_id(self):
        db = get_db_alias_for_partitioned_doc('')
        with self.assertNumQueries(0, using=db), self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case('')

    def test_get_case_with_wrong_domain(self):
        case = _create_case()
        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case(case.case_id, 'wrong-domain')

    def test_get_case_by_id_missing(self):
        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case('missing_case')

    def test_get_cases(self):
        case1 = _create_case()
        case2 = _create_case()

        cases = CommCareCase.objects.get_cases(['missing_case'])
        self.assertEqual(0, len(cases))

        cases = CommCareCase.objects.get_cases([case1.case_id])
        self.assertEqual(1, len(cases))
        self.assertEqual(case1.case_id, cases[0].case_id)

        cases = CommCareCase.objects.get_cases([case1.case_id, case2.case_id], ordered=True)
        self.assertEqual(2, len(cases))
        self.assertEqual(case1.case_id, cases[0].case_id)
        self.assertEqual(case2.case_id, cases[1].case_id)

    def test_iter_cases(self):
        case1 = _create_case()
        case2 = _create_case()
        case_ids = {'missing_case', case1.case_id, case2.case_id, '', None}

        result = CommCareCase.objects.iter_cases(case_ids, DOMAIN)
        self.assertEqual({r.case_id for r in result}, {case1.case_id, case2.case_id})

    def test_get_case_ids_that_exist(self):
        case1 = _create_case()
        case2 = _create_case()

        case_ids = CommCareCase.objects.get_case_ids_that_exist(
            DOMAIN,
            ['missing_case', case1.case_id, case2.case_id]
        )
        self.assertItemsEqual(case_ids, [case1.case_id, case2.case_id])


def _create_case(domain=DOMAIN, form_id=None, case_type=None, user_id='user1', closed=False, case_id=None):
    """Create case and related models directly (not via form processor)

    :return: CommCareCase
    """
    form_id = form_id or uuid.uuid4().hex
    case_id = case_id or uuid.uuid4().hex
    utcnow = datetime.utcnow()
    form = XFormInstance(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=domain
    )
    case = CommCareCase(
        case_id=case_id,
        domain=domain,
        type=case_type or '',
        owner_id=user_id,
        opened_on=utcnow,
        modified_on=utcnow,
        modified_by=user_id,
        server_modified_on=utcnow,
        closed=closed or False
    )
    case.track_create(CaseTransaction.form_transaction(case, form, utcnow))
    FormProcessorSQL.save_processed_models(ProcessedForms(form, None), [case])
    return case
