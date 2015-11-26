from django.test import TestCase
import os
from django.test.testcases import SimpleTestCase
from django.test.utils import override_settings
from casexml.apps.case.xml import V3
from casexml.apps.phone.tests.utils import generate_restore_payload
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper import submit_form_locally
from casexml.apps.case.tests.util import check_xml_line_by_line, delete_all_cases, delete_all_sync_logs
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.restore import FileRestoreResponse
from casexml.apps.phone.tests.dummy import dummy_restore_xml, dummy_user


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class OtaV3RestoreTest(TestCase):
    """Tests OTA Restore v3"""

    def setUp(self):
        self.domain = 'dummy-project'
        delete_all_cases()
        delete_all_sync_logs()

    def testUserRestoreWithCase(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "create_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        submit_form_locally(xml_data, self.domain)

        expected_case_block = """
        <case case_id="asdf" date_modified="2010-06-29T13:42:50.000000Z" user_id="foo"
            xmlns="http://commcarehq.org/case/transaction/v2">
            <create>
                <case_type>test_case_type</case_type>
                <case_name>test case name</case_name>
                <owner_id>foo</owner_id>
            </create>
            <update>
                <external_id>someexternal</external_id>
            </update>
        </case>"""

        restore_payload = generate_restore_payload(
            project=Domain(name=self.domain),
            user=dummy_user(),
            items=True,
            version=V3
        )
        sync_log_id = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).one().get_id
        check_xml_line_by_line(
            self,
            dummy_restore_xml(sync_log_id, expected_case_block, items=4),
            restore_payload
        )


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
