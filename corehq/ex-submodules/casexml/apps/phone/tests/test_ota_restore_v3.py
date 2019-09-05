import six
from django.test import TestCase
from django.test.testcases import SimpleTestCase
from django.test.utils import override_settings
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.domain.models import Domain
from casexml.apps.case.tests.util import (
    delete_all_cases,
    delete_all_sync_logs,
)
from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.restore import RestoreContent
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.utils import MockDevice


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


class TestRestoreContent(SimpleTestCase):

    def _expected(self, username, body, items=None):
        items_text = (' items="%s"' % items) if items is not None else ''
        return (
            '<OpenRosaResponse xmlns="http://openrosa.org/http/response"%(items)s>'
            '<message nature="ota_restore_success">Successfully restored account %(username)s!</message>'
            '%(body)s'
            '</OpenRosaResponse>'
        ) % {
            "username": username,
            "body": body,
            "items": items_text,
        }

    def test_no_items(self):
        user = 'user1'
        body = '<elem>data0</elem>'
        expected = self._expected(user, body, items=None)
        with RestoreContent(user, False) as response:
            response.append(body.encode('utf-8'))
            with response.get_fileobj() as fileobj:
                self.assertEqual(expected, fileobj.read().decode('utf-8'))

    def test_items(self):
        user = 'user1'
        body = '<elem>data0</elem>'
        expected = self._expected(user, body, items=2)
        with RestoreContent(user, True) as response:
            response.append(body.encode('utf-8'))
            with response.get_fileobj() as fileobj:
                self.assertEqual(expected, fileobj.read().decode('utf-8'))
