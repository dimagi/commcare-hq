from django.test import TestCase

from casexml.apps.case.mock.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.form_processor.tests.utils import use_sql_backend, FormProcessorTestUtils
from custom.icds.management.commands.close_duplicate_delegates import get_issue_cases_with_duplicates, \
    get_delegate_case_ids_to_close


@use_sql_backend
class TestDeleteDuplicateDelegates(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestDeleteDuplicateDelegates, cls).setUpClass()
        factory = CaseFactory(domain='icds-cas')
        # create parent cases
        factory.create_or_update_cases([
            CaseStructure(case_id='tech-issue1', attrs={'create': True, 'case_type': 'tech_issue'}),
            CaseStructure(case_id='tech-issue2', attrs={'create': True, 'case_type': 'tech_issue'})
        ])
        # first round of child cases
        factory.create_or_update_cases([
            CaseStructure(
                case_id='tech_issue_delegate1',
                attrs={'create': True, 'case_type': 'tech_issue_delegate'},
                indices=[CaseIndex(
                    CaseStructure(case_id='tech-issue1', attrs={'create': False}),
                    identifier='issue',
                    relationship='child',
                    related_type='tech_issue',
                )]
            ),
            CaseStructure(
                case_id='tech_issue_delegate3',
                attrs={'create': True, 'case_type': 'tech_issue_delegate'},
                indices=[CaseIndex(
                    CaseStructure(case_id='tech-issue2', attrs={'create': False}),
                    identifier='issue',
                    relationship='child',
                    related_type='tech_issue',
                )]
            )
        ])

        # create duplicate delegate case for tech_issue1
        factory.create_or_update_cases([
            CaseStructure(
                case_id='tech_issue_delegate2',
                attrs={'create': True, 'case_type': 'tech_issue_delegate'},
                indices=[CaseIndex(
                    CaseStructure(case_id='tech-issue1', attrs={'create': False}),
                    identifier='issue',
                    relationship='child',
                    related_type='tech_issue',
                )]
            )
        ])

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        super(TestDeleteDuplicateDelegates, cls).tearDownClass()

    def test_get_issue_cases_with_duplicates(self):
        case_ids = get_issue_cases_with_duplicates('default', 'icds-cas')
        self.assertEqual({'tech-issue1'}, case_ids)

    def test_get_case_ids_to_delete(self):
        case_ids = get_delegate_case_ids_to_close('default', ['tech-issue1'])
        self.assertEqual(case_ids, {'tech_issue_delegate1'})
