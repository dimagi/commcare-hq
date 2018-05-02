from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username


class OtaRestoreBugTest(TestCase):

    def setUp(self):
        delete_all_users()

    def test_cross_domain_assignments(self):
        good_domain = 'main-domain'
        domain = create_domain(good_domain)
        bad_domain = 'bad-domain'
        create_domain(bad_domain)
        user = CommCareUser.create(good_domain, format_username('user', good_domain), 'secret')

        def _submit_case(domain):
            case_id = uuid.uuid4().hex
            case_block = CaseBlock(
                create=True,
                case_id=case_id,
                case_name='donald',
                case_type='duck',
                user_id=user._id,
                owner_id=user._id,
            ).as_xml()
            _, [case] = post_case_blocks([case_block], {'domain': domain})
            return case

        good_case = _submit_case(good_domain)

        # create a case in the "wrong" domain
        # in the future this should actually fail completely
        bad_case = _submit_case(bad_domain)

        self.assertEqual(good_domain, good_case.domain)
        self.assertEqual(bad_domain, bad_case.domain)
        for case in (good_case, bad_case):
            self.assertEqual(user._id, case.user_id)
            self.assertEqual(user._id, case.owner_id)

        restore_config = RestoreConfig(
            project=domain,
            restore_user=user.to_ota_restore_user(),
            params=RestoreParams(version=V2),
        )
        payload = restore_config.get_payload().as_string()
        self.assertTrue(good_case._id in payload)
        self.assertFalse(bad_case._id in payload)
