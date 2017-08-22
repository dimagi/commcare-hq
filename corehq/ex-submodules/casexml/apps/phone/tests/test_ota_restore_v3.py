from django.test import TestCase
import os
from django.test.testcases import SimpleTestCase
from django.test.utils import override_settings
from casexml.apps.case.xml import V3
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.domain.models import Domain
from casexml.apps.case.tests.util import (
    delete_all_cases,
    delete_all_sync_logs,
)
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.restore import FileRestoreResponse
from casexml.apps.phone.tests.utils import create_restore_user, MockDevice


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class OtaV3RestoreTest(TestCase):
    """Tests OTA Restore v3"""

    def setUp(self):
        self.domain = 'dummy-project'
        self.project = Domain(name=self.domain)
        self.project.save()
        delete_all_cases()
        delete_all_sync_logs()
        delete_all_users()

    def tearDown(self):
        self.project.delete()

    def testUserRestoreWithCase(self):
        restore_user = create_restore_user(domain=self.domain)
        case_id = 'my-case-id'
        device = MockDevice(self.project, restore_user)
        device.change_cases(CaseBlock(
            create=True,
            case_id=case_id,
            user_id=restore_user.user_id,
            owner_id=restore_user.user_id,
            case_type='test-case-type',
            update={'external_id': 'someexternal'},
        ))
        self.assertIn(case_id, device.sync().cases)


class TestRestoreResponse(SimpleTestCase):

    def _expected(self, username, body, items=None):
        items_text = ' items="{}"'.format(items) if items is not None else ''
        return (
            '<OpenRosaResponse xmlns="http://openrosa.org/http/response"{items}>'
            '<message nature="ota_restore_success">Successfully restored account {username}!</message>'
            '{body}'
            '</OpenRosaResponse>'
        ).format(
            username=username,
            body=body,
            items=items_text
        )

    def test_no_items(self):
        user = 'user1'
        body = '<elem>data0</elem>'
        expected = self._expected(user, body, items=None)
        with FileRestoreResponse(user, False) as response:
            response.append(body)
            response.finalize()
            self.assertEqual(expected, str(response))

    def test_items(self):
        user = 'user1'
        body = '<elem>data0</elem>'
        expected = self._expected(user, body, items=2)
        response = FileRestoreResponse(user, True)
        response.append(body)
        response.finalize()
        self.assertEqual(expected, str(response))

    def test_add(self):
        user = 'user1'
        body1 = '<elem>data0</elem>'
        body2 = '<elem>data1</elem>'
        expected = self._expected(user, body1 + body2, items=3)
        response1 = FileRestoreResponse(user, True)
        response1.append(body1)

        response2 = FileRestoreResponse(user, True)
        response2.append(body2)

        added = response1 + response2
        added.finalize()
        self.assertEqual(expected, str(added))
