from datetime import datetime
import uuid

from django.core.management import call_command
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.util import post_case_blocks

from corehq.apps.app_manager.util import enable_usercase
from corehq.apps.callcenter.sync_user_case import sync_user_cases
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class CaseCommandsTest(TestCase):
    domain = 'cases-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()

        cls.domain_obj = create_domain(cls.domain)
        enable_usercase(cls.domain)

        cls.factory = CaseFactory(domain=cls.domain)
        cls.case_accessor = CaseAccessors(cls.domain)

        username = normalize_username("mobile_worker_1", cls.domain)
        cls.mobile_worker = CommCareUser.create(cls.domain, username, "123", None, None)
        cls.user_id = cls.mobile_worker.user_id
        sync_user_cases(cls.mobile_worker)
        cls.mobile_worker.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        delete_all_users()
        super().tearDown()

    def test_invalid_username(self):
        with self.assertRaises(Exception):
            call_command('add_hq_user_id_to_case', self.domain, 'checkin', '--username=afakeuserthatdoesnotexist')

    def submit_case_block(self, create, case_id, **kwargs):
        return post_case_blocks(
            [
                CaseBlock.deprecated_init(
                    create=create,
                    case_id=case_id,
                    **kwargs
                ).as_xml()
            ], domain=self.domain
        )

    def test_add_hq_user_id_to_case(self):
        checkin_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, checkin_case_id, user_id=self.user_id, case_type='checkin',
            update={"username": self.mobile_worker.raw_username, "hq_user_id": None}
        )
        lab_result_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, lab_result_case_id, user_id=self.user_id, case_type='lab_result',
            update={"username": self.mobile_worker.raw_username, "hq_user_id": None}
        )
        checkin_case = self.case_accessor.get_case(checkin_case_id)
        self.assertEqual('', checkin_case.get_case_property('hq_user_id'))
        self.assertEqual(checkin_case.username, 'mobile_worker_1')

        call_command('add_hq_user_id_to_case', self.domain, 'checkin')

        checkin_case = self.case_accessor.get_case(checkin_case_id)
        lab_result_case = self.case_accessor.get_case(lab_result_case_id)
        self.assertEqual(checkin_case.get_case_property('hq_user_id'), self.user_id)
        self.assertEqual(lab_result_case.hq_user_id, '')

    def test_update_case_index_relationship(self):
        patient_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_id, user_id=self.user_id, owner_id='owner1', case_type='patient',
        )

        lab_result_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, lab_result_case_id, user_id=self.user_id, owner_id='owner1', case_type='lab_result',
            index={'patient': ('patient', patient_case_id, 'child')}
        )

        lab_result_case = self.case_accessor.get_case(lab_result_case_id)
        self.assertEqual(lab_result_case.indices[0].referenced_type, 'patient')
        self.assertEqual(lab_result_case.indices[0].relationship, 'child')

        call_command('update_case_index_relationship', self.domain, 'lab_result')

        lab_result_case = self.case_accessor.get_case(lab_result_case_id)
        self.assertEqual(lab_result_case.indices[0].relationship, 'extension')
