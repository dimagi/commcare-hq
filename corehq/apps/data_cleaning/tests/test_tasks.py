from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from corehq.apps.data_cleaning.models import (
    BulkEditChange,
    BulkEditRecord,
    BulkEditSessionType,
    BulkEditSession,
    EditActionType,
)
from corehq.apps.data_cleaning.tasks import commit_data_cleaning
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import flag_enabled


@flag_enabled('DATA_CLEANING_CASES')
class CommitCasesTest(TestCase):
    case_type = 'song'

    def setUp(self):
        self.domain = create_domain('the-loveliest-time')
        self.addCleanup(self.domain.delete)

        self.web_user = WebUser.create(
            domain=self.domain.name,
            username='crj123',
            password='shhh',
            created_by=None,
            created_via=None,
        )
        self.addCleanup(self.web_user.delete, self.domain.name, deleted_by=None)

        factory = CaseFactory(domain=self.domain.name)
        self.case = factory.create_case(
            case_type=self.case_type,
            owner_id='crj123',
            case_name='Shadow',
            update={'speed': 'slow'},
        )

        self.session = BulkEditSession(
            domain=self.domain.name,
            user=self.web_user.get_django_user(),
            session_type=BulkEditSessionType.CASE,
            identifier=self.case_type,
        )
        self.session.save()

        super().setUp()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test_commit_case(self):
        record = BulkEditRecord(
            session=self.session,
            doc_id=self.case.case_id,
        )
        record.save()

        change = BulkEditChange(
            session=self.session,
            prop_id='speed',
            action_type=EditActionType.UPPER_CASE,
        )
        change.save()
        change.records.add(record)

        commit_data_cleaning(self.session.session_id)

        self.assertEqual(self.case.get_case_property('speed'), 'slow')
