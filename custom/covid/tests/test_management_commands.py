from django.core.management import call_command
from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

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

        cls.checkin_case1 = cls.factory.create_case(
            case_type="checkin",
            owner_id=cls.mobile_worker.get_id,
            update={"username": cls.mobile_worker.raw_username,
                    "hq_user_id": None}
        )
        cls.lab_result_case1 = cls.factory.create_case(
            case_type="lab_result",
            owner_id=cls.mobile_worker.get_id,
            update={"username": cls.mobile_worker.raw_username,
                    "hq_user_id": None},
        )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        delete_all_users()
        super().tearDown()

    def test_add_hq_user_id_to_case(self):
        checkin_case_first = self.case_accessor.get_case(self.checkin_case1.case_id)
        self.assertEqual('', checkin_case_first.get_case_property('hq_user_id'))
        self.assertEqual(checkin_case_first.username, 'mobile_worker_1')

        call_command('add_hq_user_id_to_case', self.domain, None)

        checkin_case_first = self.case_accessor.get_case(self.checkin_case1.case_id)
        lab_result_case_first = self.case_accessor.get_case(self.lab_result_case1.case_id)

        self.assertEqual(checkin_case_first.get_case_property('hq_user_id'), self.user_id)
        self.assertEqual(lab_result_case_first.hq_user_id, '')
