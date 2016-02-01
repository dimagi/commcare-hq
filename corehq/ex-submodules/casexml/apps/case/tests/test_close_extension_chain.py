from datetime import datetime

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.dbaccessors import get_extension_chain
from casexml.apps.case.xform import get_extensions_to_close
from casexml.apps.phone.models import User
from casexml.apps.phone.tests.test_sync_mode import SyncBaseTest
from corehq.apps.domain.models import Domain
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import flag_enabled


class AutoCloseExtensionsTest(SyncBaseTest):
    def setUp(self):
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()
        self.domain = "domain"
        self.project = Domain(name=self.domain)
        self.user = User(user_id='user', username='name', password="changeme",
                         date_joined=datetime(2011, 6, 9))
        self.factory = CaseFactory()
        self.extension_ids = ['1', '2', '3']
        self.host = CaseStructure(case_id='host')
        self.extension = CaseStructure(
            case_id=self.extension_ids[0],
            indices=[CaseIndex(
                related_structure=self.host,
                relationship="extension",
            )],
        )
        self.extension_2 = CaseStructure(
            case_id=self.extension_ids[1],
            indices=[CaseIndex(
                related_structure=self.extension,
                relationship="extension",
            )],
        )
        self.extension_3 = CaseStructure(
            case_id=self.extension_ids[2],
            indices=[CaseIndex(
                related_structure=self.extension_2,
                relationship="extension",
            )],
        )

    def test_get_extension_chain_simple(self):
        self.factory.create_or_update_cases([self.extension])
        self.assertEqual(set(self.extension_ids[0]), get_extension_chain([self.host], self.domain))

    def test_get_extension_chain_multiple(self):
        self.factory.create_or_update_cases([self.extension_3])
        self.assertEqual(set(self.extension_ids),
                         get_extension_chain([self.host], self.domain))

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_get_extension_to_close(self):
        """should return empty if case is not a host, otherwise should return full chain"""
        created_cases = self.factory.create_or_update_cases([self.extension_3])
        # host open, should be empty
        no_cases = get_extensions_to_close(created_cases[-1], self.domain)
        self.assertEqual(set(), no_cases)

        created_cases[-1] = self.factory.create_or_update_case(CaseStructure(
            case_id=self.host.case_id,
            attrs={'close': True}
        ))[0]

        # host closed, should get full chain
        full_chain = get_extensions_to_close(created_cases[-1], self.domain)
        self.assertEqual(set(self.extension_ids), full_chain)

        # extension (not a host), should be empty
        no_cases = get_extensions_to_close(created_cases[2], self.domain)
        self.assertEqual(set(), no_cases)

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_close_cases(self):
        """Closing a host should close all the extensions"""
        self.factory.create_or_update_cases([self.extension_3])
        self.assertFalse(CommCareCase.get(self.extension.case_id).closed)
        self.assertFalse(CommCareCase.get(self.extension_2.case_id).closed)
        self.assertFalse(CommCareCase.get(self.extension_3.case_id).closed)

        self.factory.create_or_update_case(CaseStructure(
            case_id=self.extension.case_id,
            attrs={'close': True}
        ))
        self.assertFalse(CommCareCase.get(self.host.case_id).closed)
        self.assertTrue(CommCareCase.get(self.extension.case_id).closed)
        self.assertFalse(CommCareCase.get(self.extension_2.case_id).closed)
        self.assertFalse(CommCareCase.get(self.extension_3.case_id).closed)

        self.factory.create_or_update_case(CaseStructure(
            case_id=self.host.case_id,
            attrs={'close': True}
        ))
        self.assertTrue(CommCareCase.get(self.host.case_id).closed)
        self.assertTrue(CommCareCase.get(self.extension.case_id).closed)
        self.assertTrue(CommCareCase.get(self.extension_2.case_id).closed)
        self.assertTrue(CommCareCase.get(self.extension_3.case_id).closed)
