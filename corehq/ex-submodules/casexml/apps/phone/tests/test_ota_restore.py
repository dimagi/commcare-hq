from django.test import TestCase, SimpleTestCase
import os
import time
from django.test.utils import override_settings
from casexml.apps.phone.tests.utils import generate_restore_payload, get_restore_config
from corehq.apps.receiverwrapper import submit_form_locally
from casexml.apps.case.tests.util import check_xml_line_by_line, delete_all_cases, delete_all_sync_logs, \
    delete_all_xforms
from casexml.apps.phone.restore import RestoreConfig, CachedResponse
from datetime import datetime, date
from casexml.apps.phone.models import User, SyncLog
from casexml.apps.phone import xml
from django.contrib.auth.models import User as DjangoUser
from casexml.apps.phone.tests import const
from casexml.apps.case import const as case_const
from casexml.apps.phone.tests.dummy import dummy_restore_xml, dummy_user,\
    dummy_user_xml
from corehq.apps.custom_data_fields.models import SYSTEM_PREFIX
from corehq.apps.domain.models import Domain


class SimpleOtaRestoreTest(SimpleTestCase):

    def testRegistrationXML(self):
        check_xml_line_by_line(self, dummy_user_xml(),
                               xml.get_registration_xml(dummy_user()))

    def testNameAndNumber(self):
        user = User(
            user_id="12345",
            username="mclovin",
            password="guest",
            date_joined=datetime(2011, 6, 9),
            first_name="mclovin",
            phone_number="0019042411080",
        )
        payload = xml.get_registration_xml(user)

        def assertRegistrationData(key, val):
            if val is None:
                template = '<data key="{prefix}_{key}" />'
            else:
                template = '<data key="{prefix}_{key}">{val}</data>'
            self.assertIn(
                template.format(prefix=SYSTEM_PREFIX, key=key, val=val),
                payload,
            )

        assertRegistrationData("first_name", "mclovin")
        assertRegistrationData("last_name", None)
        assertRegistrationData("phone_number", "0019042411080")


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class OtaRestoreTest(TestCase):
    """Tests OTA Restore"""

    @classmethod
    def setUpClass(cls):
        delete_all_cases()
        delete_all_sync_logs()
        cls.project = Domain(name='ota-restore-tests')

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        delete_all_sync_logs()
        restore_config = RestoreConfig(project=self.project, user=dummy_user())
        restore_config.cache.delete(restore_config._initial_cache_key())

    def testFromDjangoUser(self):
        django_user = DjangoUser(username="foo", password="secret", date_joined=datetime(2011, 6, 9))
        django_user.save()
        user = User.from_django_user(django_user)
        self.assertEqual(str(django_user.pk), user.user_id)
        self.assertEqual("foo", user.username)
        self.assertEqual("secret", user.password)
        self.assertEqual(datetime(2011, 6, 9), user.date_joined)
        self.assertFalse(bool(user.user_data))

    def testUserRestore(self):
        self.assertEqual(0, SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).count())
        restore_payload = generate_restore_payload(self.project, dummy_user(), items=True)
        sync_log = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).one()
        check_xml_line_by_line(
            self,
            dummy_restore_xml(sync_log.get_id, items=3),
            restore_payload,
        )

    def testOverwriteCache(self):
        restore_config = get_restore_config(
            self.project, dummy_user(), items=True, force_cache=True
        )
        restore_config_cached = get_restore_config(
            self.project, dummy_user(), items=True
        )
        restore_config_overwrite = get_restore_config(
            self.project, dummy_user(), items=True, overwrite_cache=True
        )
        self.assertNotIsInstance(restore_config.get_payload(), CachedResponse)
        self.assertIsInstance(restore_config_cached.get_payload(), CachedResponse)
        self.assertNotIsInstance(restore_config_overwrite.get_payload(), CachedResponse)

        # even cached responses change the sync log id so they are not the same
        restore_payload = restore_config.get_payload().as_string()
        self.assertNotEqual(restore_payload, restore_config_cached.get_payload().as_string())
        self.assertNotEqual(restore_payload, restore_config_overwrite.get_payload().as_string())

    def testUserRestoreWithCase(self):
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "create_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        # implicit length assertion
        _, _, [newcase] = submit_form_locally(xml_data, domain=self.project.name)

        expected_case_block = """
        <case>
            <case_id>asdf</case_id>
            <date_modified>2010-06-29T13:42:50.000000Z</date_modified>
            <create>
                <case_type_id>test_case_type</case_type_id>
                <user_id>foo</user_id>
                <case_name>test case name</case_name>
                <external_id>someexternal</external_id>
            </create>
        </case>"""
        check_xml_line_by_line(self, expected_case_block, xml.get_case_xml(newcase, [case_const.CASE_ACTION_CREATE,
                                                                                     case_const.CASE_ACTION_UPDATE]))

        # check v2
        expected_v2_case_block = """
        <case case_id="asdf" date_modified="2010-06-29T13:42:50.000000Z" user_id="foo" xmlns="http://commcarehq.org/case/transaction/v2" >
            <create>
                <case_type>test_case_type</case_type>
                <case_name>test case name</case_name>
                <owner_id>foo</owner_id>
            </create>
            <update>
                <external_id>someexternal</external_id>
            </update>
        </case>"""
        check_xml_line_by_line(
            self,
            expected_v2_case_block,
            xml.get_case_xml(
                newcase,
                [case_const.CASE_ACTION_CREATE, case_const.CASE_ACTION_UPDATE],
                version="2.0",
            ),
        )

        restore_payload = generate_restore_payload(
            project=self.project,
            user=dummy_user(),
            items=True,
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

    def testSyncTokenWithItems(self):
        self._test_sync_token(items=True)

    def testSyncTokenWithoutItems(self):
        self._test_sync_token(items=False)

    def _test_sync_token(self, items):
        """
        Tests sync token / sync mode support
        """
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "create_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        submit_form_locally(xml_data, domain=self.project.name)

        time.sleep(1)
        restore_payload = generate_restore_payload(self.project, dummy_user(), items=items)

        sync_log_id = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False
        ).one().get_id
        expected_restore_payload = dummy_restore_xml(
            sync_log_id,
            const.CREATE_SHORT,
            items=4 if items else None,
        )
        check_xml_line_by_line(self, expected_restore_payload, restore_payload)

        time.sleep(1)
        sync_restore_payload = generate_restore_payload(
            project=self.project,
            user=dummy_user(),
            restore_id=sync_log_id,
            items=items,
        )
        all_sync_logs = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).all()
        [latest_log] = [log for log in all_sync_logs
                        if log.get_id != sync_log_id]

        # should no longer have a case block in the restore XML
        check_xml_line_by_line(
            self,
            dummy_restore_xml(latest_log.get_id, items=3 if items else None),
            sync_restore_payload,
        )

        # apply an update
        time.sleep(1)
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "update_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        submit_form_locally(xml_data, domain=self.project.name)

        time.sleep(1)
        sync_restore_payload = generate_restore_payload(
            self.project,
            user=dummy_user(),
            restore_id=latest_log.get_id,
            items=items,
        )
        all_sync_logs = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).all()
        [even_latest_log] = [log for log in all_sync_logs
                             if log.get_id != sync_log_id and
                             log.get_id != latest_log.get_id]

        # case block should come back
        expected_sync_restore_payload = dummy_restore_xml(
            even_latest_log.get_id,
            const.UPDATE_SHORT,
            items=4 if items else None,
        )
        check_xml_line_by_line(self, expected_sync_restore_payload,
                               sync_restore_payload)

    def testRestoreAttributes(self):
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "attributes.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        _, _, [newcase] = submit_form_locally(xml_data, domain=self.project.name)

        self.assertTrue(isinstance(newcase.adate, dict))
        self.assertEqual(date(2012, 02, 01), newcase.adate["#text"])
        self.assertEqual("i am an attribute", newcase.adate["@someattr"])
        self.assertTrue(isinstance(newcase.dateattr, dict))
        self.assertEqual("this shouldn't break", newcase.dateattr["#text"])
        self.assertEqual(date(2012, 01, 01), newcase.dateattr["@somedate"])
        self.assertTrue(isinstance(newcase.stringattr, dict))
        self.assertEqual("neither should this", newcase.stringattr["#text"])
        self.assertEqual("i am a string", newcase.stringattr["@somestring"])
        restore_payload = generate_restore_payload(self.project, dummy_user())
        # ghetto
        self.assertTrue('<dateattr somedate="2012-01-01">' in restore_payload)
        self.assertTrue('<stringattr somestring="i am a string">' in restore_payload)
