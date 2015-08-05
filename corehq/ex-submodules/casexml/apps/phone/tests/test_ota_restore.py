import uuid
from django.test import TestCase
import os
import time
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseRelationship
from casexml.apps.case.xml import V2
from casexml.apps.phone.data_providers.case.batched import BatchedCaseSyncOperation
from casexml.apps.phone.tests.utils import generate_restore_payload
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case.tests.util import check_xml_line_by_line, delete_all_cases, delete_all_sync_logs, \
    assert_user_has_cases, assert_user_has_case, assert_user_doesnt_have_case
from casexml.apps.phone.restore import RestoreConfig, RestoreState, RestoreParams
from casexml.apps.case.xform import process_cases
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


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class OtaRestoreTest(TestCase):
    """Tests OTA Restore"""

    @classmethod
    def setUpClass(cls):
        delete_all_cases()
        delete_all_sync_logs()
        cls.project = Domain(name='ota-restore-tests')

    def tearDown(self):
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
        restore_payload = generate_restore_payload(
            self.project, dummy_user(), items=True, force_cache=True
        )
        restore_payload_cached = generate_restore_payload(
            self.project, dummy_user(), items=True
        )
        restore_payload_overwrite = generate_restore_payload(
            self.project, dummy_user(), items=True, overwrite_cache=True
        )
        self.assertEqual(restore_payload, restore_payload_cached)
        self.assertNotEqual(restore_payload, restore_payload_overwrite)

    def testUserRestoreWithCase(self):
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "create_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data, domain=self.project.name)
        # implicit length assertion
        [newcase] = process_cases(form)
        user = dummy_user()

        self.assertEqual(1, len(list(
            BatchedCaseSyncOperation(RestoreState(self.project, user, RestoreParams())).get_all_case_updates()
        )))
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

    def test_restore_with_bad_index_ref_blows_away(self):
        user = dummy_user()
        user.domain = self.project.name
        factory = CaseFactory(
            self.project.name,
            case_defaults={
                'user_id': user.user_id,
                'owner_id': user.user_id,
                'case_type': 'a-case',
            },
        )
        # create a parent/child set of cases
        parent_id, child_id = [uuid.uuid4().hex for i in range(2)]
        child, parent = factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            relationships=[
                 CaseRelationship(CaseStructure(case_id=parent_id))
            ]
        ))
        assert_user_has_cases(self, user, [parent_id, child_id])

        # delete the parent
        parent.doc_type = 'CommCareCase-Deleted'
        parent.save()

        # check cases in payload
        assert_user_has_case(self, user, child_id)
        assert_user_doesnt_have_case(self, user, parent_id)

        # also ensure parent_id isn't in payload - e.g. in an index
        self.assertTrue(parent_id not in generate_restore_payload(
            project=self.project,
            version=V2,
            user=user,
            items=True,
        ), 'Deleting parent should remove index from the restore!')


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
        form = post_xform_to_couch(xml_data, domain=self.project.name)
        process_cases(form)

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
        form = post_xform_to_couch(xml_data, domain=self.project.name)
        process_cases(form)

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
        form = post_xform_to_couch(xml_data, domain=self.project.name)
        [newcase] = process_cases(form)
        
        self.assertTrue(isinstance(newcase.adate, dict))
        self.assertEqual(date(2012,02,01), newcase.adate["#text"])
        self.assertEqual("i am an attribute", newcase.adate["@someattr"])
        self.assertTrue(isinstance(newcase.dateattr, dict))
        self.assertEqual("this shouldn't break", newcase.dateattr["#text"])
        self.assertEqual(date(2012,01,01), newcase.dateattr["@somedate"])
        self.assertTrue(isinstance(newcase.stringattr, dict))
        self.assertEqual("neither should this", newcase.stringattr["#text"])
        self.assertEqual("i am a string", newcase.stringattr["@somestring"])
        restore_payload = generate_restore_payload(self.project, dummy_user())
        # ghetto
        self.assertTrue('<dateattr somedate="2012-01-01">' in restore_payload)
        self.assertTrue('<stringattr somestring="i am a string">' in restore_payload)
