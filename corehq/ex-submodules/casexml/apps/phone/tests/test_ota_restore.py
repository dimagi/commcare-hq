import os
import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache

from casexml.apps.case import const as case_const
from casexml.apps.case.tests.util import (
    check_xml_line_by_line,
    delete_all_cases,
    delete_all_sync_logs,
    delete_all_xforms,
)
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests.util import make_loc
from casexml.apps.phone import xml
from casexml.apps.phone.models import SyncLogSQL, properly_wrap_sync_log
from casexml.apps.phone.restore import CachedResponse
from casexml.apps.phone.tests import const
from casexml.apps.phone.tests.dummy import dummy_restore_xml, dummy_user_xml
from casexml.apps.phone.tests.utils import (
    create_restore_user,
    deprecated_generate_restore_payload,
)
from casexml.apps.phone.utils import get_restore_config, MockDevice
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.util import normalize_username
from corehq.util.test_utils import TestFileMixin


def get_registration_xml(restore_user):
    return xml.tostring(xml.get_registration_element(restore_user)).decode('utf-8')


def _expected_payload(key, val):
    if val is None:
        expected = f'<data key="{key}"/>'
    else:
        expected = f'<data key="{key}">{val}</data>'
    return expected


class SimpleOtaRestoreTest(TestCase):

    def setUp(self):
        super(SimpleOtaRestoreTest, self).setUp()
        delete_all_users()

    def tearDown(self):
        delete_all_users()
        super(SimpleOtaRestoreTest, self).tearDown()

    def test_registration_xml(self):
        user = create_restore_user()
        check_xml_line_by_line(self, dummy_user_xml(user),
                               get_registration_xml(user))

    def test_username_doesnt_have_domain(self):
        user = create_restore_user(username=normalize_username('withdomain', domain='thedomain'))
        restore_payload = get_registration_xml(user)
        self.assertTrue('thedomain' not in restore_payload)

    def test_name_and_number(self):
        user = create_restore_user(
            first_name='mclovin',
            last_name=None,
            phone_number='555555',
        )
        payload = get_registration_xml(user)
        self.assertIn(_expected_payload("commcare_first_name", "mclovin"), payload)
        self.assertIn(_expected_payload("commcare_last_name", None), payload)
        self.assertIn(_expected_payload("commcare_phone_number", "555555"), payload)
        self.assertIn(_expected_payload("commcare_user_type", "commcare"), payload)


class BaseOtaRestoreTest(TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super(BaseOtaRestoreTest, cls).setUpClass()
        delete_all_cases()
        delete_all_sync_logs()
        cls.project = Domain(name='ota-restore-tests')
        cls.project.save()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(BaseOtaRestoreTest, cls).tearDownClass()

    def setUp(self):
        super(BaseOtaRestoreTest, self).setUp()
        delete_all_users()
        self.restore_user = create_restore_user(self.project.name)

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        delete_all_sync_logs()
        get_redis_default_cache().clear()
        super(BaseOtaRestoreTest, self).tearDown()


class OtaRestoreTest(BaseOtaRestoreTest):

    def _get_the_first_synclog(self):
        return properly_wrap_sync_log(SyncLogSQL.objects.first().doc)

    def _get_synclog_count(self):
        return SyncLogSQL.objects.count()

    def test_user_restore(self):
        self.assertEqual(0, self._get_synclog_count())
        restore_payload = deprecated_generate_restore_payload(
            self.project, self.restore_user, items=True)
        sync_log = self._get_the_first_synclog()
        check_xml_line_by_line(
            self,
            dummy_restore_xml(sync_log.get_id, items=3, user=self.restore_user),
            restore_payload,
        )

    def testOverwriteCache(self):
        restore_config = get_restore_config(
            self.project, self.restore_user, items=True, force_cache=True
        )
        restore_config_cached = get_restore_config(
            self.project, self.restore_user, items=True
        )
        restore_config_overwrite = get_restore_config(
            self.project, self.restore_user, items=True, overwrite_cache=True
        )
        self.assertNotIsInstance(restore_config.get_payload(), CachedResponse)
        self.assertIsInstance(restore_config_cached.get_payload(), CachedResponse)
        self.assertNotIsInstance(restore_config_overwrite.get_payload(), CachedResponse)

    def testDifferentDeviceCache(self):
        '''
        Ensure that if restore is coming from different device, do not return cached response
        '''
        restore_config = get_restore_config(
            self.project, self.restore_user, items=True, force_cache=True, device_id='123',
        )
        restore_config_other_device = get_restore_config(
            self.project, self.restore_user, items=True, device_id='456'
        )

        self.assertNotIsInstance(restore_config.get_payload(), CachedResponse)
        self.assertNotIsInstance(restore_config_other_device.get_payload(), CachedResponse)

    def testUserRestoreWithCase(self):
        xml_data = self.get_xml('create_short').decode('utf-8')
        xml_data = xml_data.format(user_id=self.restore_user.user_id)

        # implicit length assertion
        result = submit_form_locally(xml_data, domain=self.project.name)

        expected_case_block = """
        <case>
            <case_id>asdf</case_id>
            <date_modified>2010-06-29T13:42:50.000000Z</date_modified>
            <create>
                <case_type_id>test_case_type</case_type_id>
                <user_id>{user_id}</user_id>
                <case_name>test case name</case_name>
                <external_id>someexternal</external_id>
            </create>
            <update>
                <owner_id>{user_id}</owner_id>
                <date_opened>2010-06-29</date_opened>
            </update>
        </case>""".format(user_id=self.restore_user.user_id)
        check_xml_line_by_line(
            self,
            expected_case_block,
            xml.get_case_xml(
                result.case,
                [case_const.CASE_ACTION_CREATE, case_const.CASE_ACTION_UPDATE]
            )
        )

        # check v2
        expected_v2_case_block = """
        <case case_id="asdf" user_id="{user_id}" date_modified="2010-06-29T13:42:50.000000Z" xmlns="http://commcarehq.org/case/transaction/v2" >
            <create>
                <case_type>test_case_type</case_type>
                <case_name>test case name</case_name>
                <owner_id>{user_id}</owner_id>
            </create>
            <update>
                <external_id>someexternal</external_id>
                <date_opened>2010-06-29</date_opened>
            </update>
        </case>""".format(user_id=self.restore_user.user_id)
        check_xml_line_by_line(
            self,
            expected_v2_case_block,
            xml.get_case_xml(
                result.case,
                [case_const.CASE_ACTION_CREATE, case_const.CASE_ACTION_UPDATE],
                version="2.0",
            ),
        )

        restore_payload = deprecated_generate_restore_payload(
            project=self.project,
            user=self.restore_user,
            items=True,
        )
        sync_log_id = self._get_the_first_synclog().get_id
        check_xml_line_by_line(
            self,
            dummy_restore_xml(sync_log_id, expected_case_block, items=4, user=self.restore_user),
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
        def get_all_syncslogs():
            return [properly_wrap_sync_log(log.doc) for log in SyncLogSQL.objects.all()]

        xml_data = self.get_xml('create_short').decode('utf-8')
        xml_data = xml_data.format(user_id=self.restore_user.user_id)
        submit_form_locally(xml_data, domain=self.project.name)

        restore_payload = deprecated_generate_restore_payload(
            self.project, self.restore_user, items=items)

        sync_log_id = SyncLogSQL.objects.filter(
            user_id=self.restore_user.user_id
        ).order_by('date').last().synclog_id.hex
        expected_restore_payload = dummy_restore_xml(
            sync_log_id,
            const.CREATE_SHORT.format(user_id=self.restore_user.user_id),
            items=4 if items else None,
            user=self.restore_user,
        )
        check_xml_line_by_line(self, expected_restore_payload, restore_payload)

        sync_restore_payload = deprecated_generate_restore_payload(
            project=self.project,
            user=self.restore_user,
            restore_id=sync_log_id,
            items=items,
        )
        all_sync_logs = get_all_syncslogs()

        [latest_log] = [log for log in all_sync_logs
                        if log.get_id != sync_log_id]

        # should no longer have a case block in the restore XML
        check_xml_line_by_line(
            self,
            dummy_restore_xml(
                latest_log.get_id,
                items=3 if items else None,
                user=self.restore_user,
            ),
            sync_restore_payload,
        )

        # apply an update
        xml_data = self.get_xml('update_short').decode('utf-8')
        xml_data = xml_data.format(user_id=self.restore_user.user_id)
        submit_form_locally(xml_data, domain=self.project.name)

        sync_restore_payload = deprecated_generate_restore_payload(
            self.project,
            user=self.restore_user,
            restore_id=latest_log.get_id,
            items=items,
        )
        all_sync_logs = get_all_syncslogs()
        [even_latest_log] = [log for log in all_sync_logs
                             if log.get_id != sync_log_id
                             and log.get_id != latest_log.get_id]

        # case block should come back
        expected_sync_restore_payload = dummy_restore_xml(
            even_latest_log.get_id,
            const.UPDATE_SHORT.format(user_id=self.restore_user.user_id),
            items=4 if items else None,
            user=self.restore_user
        )
        check_xml_line_by_line(self, expected_sync_restore_payload,
                               sync_restore_payload)

    def testRestoreAttributes(self):
        xml_data = self.get_xml('attributes').decode('utf-8')
        xml_data = xml_data.format(user_id=self.restore_user.user_id)
        newcase = submit_form_locally(xml_data, domain=self.project.name).case

        self.assertTrue(isinstance(newcase.case_json['adate'], dict))
        self.assertEqual('2012-02-01', newcase.case_json['adate']["#text"])
        self.assertEqual("i am an attribute", newcase.case_json['adate']["@someattr"])
        self.assertTrue(isinstance(newcase.case_json['dateattr'], dict))
        self.assertEqual("this shouldn't break", newcase.case_json['dateattr']["#text"])
        self.assertEqual('2012-01-01', newcase.case_json['dateattr']["@somedate"])
        self.assertTrue(isinstance(newcase.case_json['stringattr'], dict))
        self.assertEqual("neither should this", newcase.case_json['stringattr']["#text"])
        self.assertEqual("i am a string", newcase.case_json['stringattr']["@somestring"])
        restore_payload = deprecated_generate_restore_payload(
            self.project, self.restore_user).decode('utf-8')
        # ghetto
        self.assertIn('<dateattr somedate="2012-01-01">', restore_payload)
        self.assertIn('<stringattr somestring="i am a string">', restore_payload)

    def testRestoreDeletedIndex(self):
        device = MockDevice(self.project, self.restore_user)
        parent_id = uuid.uuid4().hex
        case_id = uuid.uuid4().hex
        device.case_factory.post_case_blocks([
            CaseBlock(
                create=True,
                case_id=parent_id,
                case_type='parent',
                case_name='parent',
                user_id=self.restore_user.user_id,
                owner_id=self.restore_user.user_id,
            ).as_text(),
            CaseBlock(
                create=True,
                case_id=case_id,
                case_type='test_case_type',
                case_name='test case name',
                user_id=self.restore_user.user_id,
                owner_id=self.restore_user.user_id,
                date_modified='2022-09-29',
                date_opened='2022-09-29',
                index={'parent': ('mother', parent_id)}
            ).as_text()
        ])
        device.sync()

        device.case_factory.post_case_blocks([
            CaseBlock(
                case_id=case_id,
                date_modified='2022-09-29',
                index={'parent': ('mother', '')}
            ).as_text()
        ])
        expected_case_block = f"""
        <fixture id="user-groups" user_id="{self.restore_user.user_id}">
          <groups/>
        </fixture>
        <case xmlns="http://commcarehq.org/case/transaction/v2"
            case_id="{case_id}"
            date_modified="2022-09-29T00:00:00.000000Z"
            user_id="{self.restore_user.user_id}">
            <update>
                <case_type>test_case_type</case_type>
                <case_name>test case name</case_name>
                <owner_id>{self.restore_user.user_id}</owner_id>
                <date_opened>2022-09-29</date_opened>
            </update>
            <index>
              <parent case_type="mother"/>
            </index>
        </case>"""
        sync = device.sync()
        check_xml_line_by_line(
            self,
            dummy_restore_xml(sync.restore_id, case_xml=expected_case_block, user=self.restore_user),
            sync.payload
        )


class WebUserOtaRestoreTest(OtaRestoreTest):
    """Tests for restore using a web user"""

    def setUp(self):
        super(WebUserOtaRestoreTest, self).setUp()
        delete_all_users()
        self.restore_user = create_restore_user(self.project.name, is_mobile_user=False)

    def test_location_ids_in_restore(self):
        web_user = self.restore_user._couch_user
        domain = self.project.name

        # Location setup
        lt = LocationType.objects.create(
            domain=domain, name='lt2'
        )
        self.loc1 = make_loc('loc1', type=lt.name, domain=domain)
        self.loc2 = make_loc('loc2', type=lt.name, domain=domain)
        web_user.set_location(domain, self.loc1)
        web_user.add_to_assigned_locations(domain, self.loc2)

        payload = get_registration_xml(self.restore_user)

        self.assertIn(_expected_payload("commcare_location_id", self.loc1.location_id), payload)
        self.assertIn(_expected_payload("commcare_location_ids",
                                       ' '.join([self.loc1.location_id, self.loc2.location_id])), payload)
        self.assertIn(_expected_payload("commcare_primary_case_sharing_id", self.loc1.location_id), payload)
