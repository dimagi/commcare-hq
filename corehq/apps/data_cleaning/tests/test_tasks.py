from datetime import datetime

from casexml.apps.case.mock import CaseFactory
from django.test import TestCase

from corehq.apps.data_cleaning.models import (
    BulkEditChange,
    BulkEditRecord,
    BulkEditSession,
    BulkEditSessionType,
    EditActionType,
)
from corehq.apps.data_cleaning.tasks import commit_data_cleaning
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import case_search_adapter, user_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils


@es_test(requires=[case_search_adapter, user_adapter], setup_class=True)
class CommitCasesTest(TestCase):
    case_type = 'song'
    domain_name = 'the-loveliest-time'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)
        case_search_es_setup(cls.domain_name, get_case_blocks())

    def setUp(self):
        self.web_user = WebUser.create(
            domain=self.domain.name,
            username='crj123',
            password='shhh',
            created_by=None,
            created_via=None,
        )
        self.addCleanup(self.web_user.delete, self.domain.name, deleted_by=None)

        self.factory = CaseFactory(domain=self.domain.name)
        self.case = self.factory.create_case(
            case_type=self.case_type,
            owner_id='crj123',
            case_name='Shadow',
            update={
                'play_count': 10,
                'speed': 'slow',
                'year': '2023',
            },
        )

        self.session = BulkEditSession(
            domain=self.domain.name,
            user=self.web_user.get_django_user(),
            session_type=BulkEditSessionType.CASE,
            identifier=self.case_type,
            committed_on=datetime.utcnow(),
        )
        self.session.save()

        super().setUp()

    def _refresh_session(self):
        self.session = BulkEditSession.objects.get(id=self.session.id)

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

        case = CommCareCase.objects.get_case(self.case.case_id, self.domain.name)
        self.assertEqual(case.get_case_property('speed'), 'SLOW')

    def test_multiple_changes(self):
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

        change = BulkEditChange(
            session=self.session,
            prop_id='speed',
            action_type=EditActionType.COPY_REPLACE,
            copy_from_prop_id='year',
        )
        change.save()
        change.records.add(record)

        form_ids = commit_data_cleaning(self.session.session_id)

        case = CommCareCase.objects.get_case(self.case.case_id, self.domain.name)
        self.assertEqual(case.get_case_property('speed'), '2023')
        self.assertEqual(case.get_case_property('year'), '2023')

        self._refresh_session()
        self.assertDictEqual(
            self.session.result,
            {
                'errors': [],
                'form_ids': form_ids,
                'num_committed_records': 1,
                'record_count': 1,
                'percent': 100,
            },
        )
        self.assertEqual(self.session.percent_complete, 100)
        self.assertListEqual(list(self.session.form_ids), form_ids)
        self.assertIsNotNone(self.session.completed_on)

    def test_chunking(self):
        cases = [self.case]
        for i in range(0, CASEBLOCK_CHUNKSIZE):
            cases.append(
                self.factory.create_case(
                    case_type=self.case_type,
                    owner_id='crj123',
                    case_name=f'case{i}',
                    update={'speed': f'{i}kph'},
                )
            )

        records = []
        for case in cases:
            records.append(
                BulkEditRecord(
                    session=self.session,
                    doc_id=case.case_id,
                )
            )
            records[-1].save()

        change = BulkEditChange(
            session=self.session,
            prop_id='speed',
            action_type=EditActionType.FIND_REPLACE,
            use_regex=True,
            find_string='$',
            replace_string='!',
        )
        change.save()
        change.records.add(*records)

        form_ids = commit_data_cleaning(self.session.session_id)
        self.assertEqual(len(form_ids), 2)

        case = CommCareCase.objects.get_case(self.case.case_id, self.domain.name)
        self.assertEqual(case.get_case_property('speed'), 'slow!')
