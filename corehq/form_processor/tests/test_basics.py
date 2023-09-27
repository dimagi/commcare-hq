import uuid
from datetime import datetime
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import deprecated_check_user_has_case
from casexml.apps.phone.restore_caching import RestorePayloadPathCache
from casexml.apps.phone.tests.utils import create_restore_user

from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.cloudcare.const import DEVICE_ID as FORMPLAYER_DEVICE_ID
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import clear_domain_names
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS, submit_case_blocks
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CouchUser
from corehq.blobs import get_blob_db
from corehq.form_processor.interfaces.processor import (
    FormProcessorInterface,
    XFormQuestionValueIterator,
)
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.form_processor.utils import get_simple_form_xml
from corehq.util.dates import coerce_to_datetime
from corehq.util.test_utils import flag_enabled

DOMAIN = 'fundamentals'


@sharded
class FundamentalBaseTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(FundamentalBaseTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        super(FundamentalBaseTests, cls).tearDownClass()

    def setUp(self):
        super(FundamentalBaseTests, self).setUp()
        self.interface = FormProcessorInterface()
        self.casedb = CommCareCase.objects
        self.formdb = XFormInstance.objects


class FundamentalFormTests(FundamentalBaseTests):
    def test_modified_on(self):
        form_id = uuid.uuid4().hex
        before = datetime.utcnow()
        xml = get_simple_form_xml(form_id)
        submit_form_locally(xml, DOMAIN)
        form = self.formdb.get_form(form_id)
        self.assertIsNotNone(form.server_modified_on)
        self.assertGreater(form.server_modified_on, before)

    def test_modified_on_archive(self):
        form_id = uuid.uuid4().hex
        submit_form_locally(get_simple_form_xml(form_id), DOMAIN)

        before = datetime.utcnow()
        form = self.formdb.get_form(form_id)
        form.archive()
        form = self.formdb.get_form(form_id)

        self.assertGreater(form.server_modified_on, before)

        before = datetime.utcnow()
        form.unarchive()
        form = self.formdb.get_form(form_id)
        self.assertGreater(form.server_modified_on, before)

    def test_modified_on_delete(self):
        form_id = uuid.uuid4().hex
        submit_form_locally(get_simple_form_xml(form_id), DOMAIN)

        before = datetime.utcnow()
        form = self.formdb.get_form(form_id)
        form.soft_delete()
        form = self.formdb.get_form(form_id)

        self.assertTrue(form.is_deleted)
        self.assertGreater(form.server_modified_on, before)

        before = form.server_modified_on

        self.formdb.soft_undelete_forms(DOMAIN, [form_id])
        form = self.formdb.get_form(form_id)

        self.assertFalse(form.is_deleted)
        self.assertGreater(form.server_modified_on, before)

    def test_deleted_on_value(self):
        form_id = uuid.uuid4().hex
        submit_form_locally(get_simple_form_xml(form_id), DOMAIN)

        before = datetime.utcnow()
        form = self.formdb.get_form(form_id)
        self.assertIsNone(form.deleted_on)

        form.soft_delete()
        form = self.formdb.get_form(form_id)
        self.assertIsNotNone(form.deleted_on)
        self.assertGreater(form.deleted_on, before)


class FundamentalCaseTests(FundamentalBaseTests):
    def test_create_case(self):
        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        xmlns = 'http://commcare.org/test_xmlns'
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=modified_on, date_opened=modified_on, update={
                'dynamic': '123'
            },
            xmlns=xmlns
        )

        case = self.casedb.get_case(case_id, DOMAIN)
        self.assertIsNotNone(case)
        self.assertEqual(case.case_id, case_id)
        self.assertEqual(case.owner_id, 'owner1')
        self.assertEqual(case.type, 'demo')
        self.assertEqual(case.name, 'create_case')
        self.assertEqual(case.opened_on, modified_on)
        self.assertEqual(case.opened_by, 'user1')
        self.assertEqual(case.modified_on, modified_on)
        self.assertEqual(case.modified_by, 'user1')
        self.assertTrue(case.server_modified_on > modified_on)
        self.assertFalse(case.closed)
        self.assertIsNone(case.closed_on)
        self.assertIsNone(case.closed_by)
        self.assertEqual(case.dynamic_case_properties()['dynamic'], '123')

        transactions = case.get_form_transactions()
        self.assertEqual(1, len(transactions))
        self.assertEqual(transactions[0].xmlns, xmlns)

    def test_create_case_unicode_name(self):
        """
        Submit case blocks with unicode names
        """
        # This was failing hard:
        # http://manage.dimagi.com/default.asp?226582#1145687

        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        case_name = 'प्रसव'
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name=case_name, date_modified=modified_on, update={
                'dynamic': '123'
            }
        )
        case = self.casedb.get_case(case_id, DOMAIN)
        self.assertEqual(case.name, case_name)

    def test_update_case(self):
        case_id = uuid.uuid4().hex
        opened_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=opened_on, update={
                'dynamic': '123'
            }
        )

        modified_on = datetime.utcnow()
        _submit_case_block(
            False, case_id, user_id='user2', owner_id='owner2',
            case_name='update_case', date_modified=modified_on, date_opened=opened_on, update={
                'dynamic': '1234'
            }
        )

        case = self.casedb.get_case(case_id, DOMAIN)
        self.assertEqual(case.owner_id, 'owner2')
        self.assertEqual(case.name, 'update_case')
        self.assertEqual(coerce_to_datetime(case.opened_on), coerce_to_datetime(opened_on))
        self.assertEqual(case.opened_by, 'user1')
        self.assertEqual(case.modified_on, modified_on)
        self.assertEqual(case.modified_by, 'user2')
        self.assertTrue(case.server_modified_on > modified_on)
        self.assertFalse(case.closed)
        self.assertIsNone(case.closed_on)
        self.assertEqual(case.dynamic_case_properties()['dynamic'], '1234')

    def test_close_case(self):
        # same as update, closed, closed on, closed by
        case_id = uuid.uuid4().hex
        opened_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=opened_on
        )

        modified_on = datetime.utcnow()
        _submit_case_block(
            False, case_id, user_id='user2', date_modified=modified_on, close=True
        )

        case = self.casedb.get_case(case_id, DOMAIN)
        self.assertEqual(case.owner_id, 'owner1')
        self.assertEqual(case.modified_on, modified_on)
        self.assertEqual(case.modified_by, 'user2')
        self.assertTrue(case.closed)
        self.assertEqual(case.closed_on, modified_on)
        self.assertEqual(case.closed_by, 'user2')
        self.assertTrue(case.server_modified_on > modified_on)

    def test_empty_update(self):
        case_id = uuid.uuid4().hex
        opened_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=opened_on, update={
                'dynamic': '123'
            }
        )

        modified_on = datetime.utcnow()
        _submit_case_block(
            False, case_id, user_id='user2', date_modified=modified_on, update={}
        )

        case = self.casedb.get_case(case_id, DOMAIN)
        self.assertEqual(case.dynamic_case_properties(), {'dynamic': '123'})

    def test_case_with_index(self):
        # same as update, indexes
        mother_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, mother_case_id, user_id='user1', owner_id='owner1', case_type='mother',
            case_name='mother', date_modified=datetime.utcnow()
        )

        child_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', mother_case_id)
            }
        )

        case = self.casedb.get_case(child_case_id, DOMAIN)
        self.assertEqual(len(case.indices), 1)
        index = case.indices[0]
        self.assertEqual(index.identifier, 'mom')
        self.assertEqual(index.referenced_id, mother_case_id)
        self.assertEqual(index.referenced_type, 'mother')
        self.assertEqual(index.relationship, 'child')

    def test_update_index(self):
        mother_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, mother_case_id, user_id='user1', owner_id='owner1', case_type='mother',
            case_name='mother', date_modified=datetime.utcnow()
        )

        child_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', mother_case_id)
            }
        )

        case = self.casedb.get_case(child_case_id, DOMAIN)
        self.assertEqual(case.indices[0].identifier, 'mom')

        _submit_case_block(
            False, child_case_id, user_id='user1', date_modified=datetime.utcnow(), index={
                'mom': ('other_mother', mother_case_id)
            }
        )
        case = self.casedb.get_case(child_case_id, DOMAIN)
        self.assertEqual(case.indices[0].referenced_type, 'other_mother')

    def test_delete_index(self):
        mother_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, mother_case_id, user_id='user1', owner_id='owner1', case_type='mother',
            case_name='mother', date_modified=datetime.utcnow()
        )

        child_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', mother_case_id)
            }
        )

        case = self.casedb.get_case(child_case_id, DOMAIN)
        self.assertEqual(len(case.indices), 1)

        _submit_case_block(
            False, child_case_id, user_id='user1', date_modified=datetime.utcnow(), index={
                'mom': ('mother', '')
            }
        )
        case = self.casedb.get_case(child_case_id, DOMAIN)
        self.assertEqual(len(case.indices), 1)
        self.assertEqual(case.indices[0].referenced_id, '')

    def test_invalid_index(self):
        invalid_case_id = uuid.uuid4().hex
        child_case_id = uuid.uuid4().hex
        form, cases = _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', invalid_case_id)
            }
        )
        self.assertEqual(0, len(cases))
        self.assertTrue(form.is_error)
        self.assertTrue('InvalidCaseIndex' in form.problem)

    def test_invalid_index_cross_domain(self):
        mother_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, mother_case_id, user_id='user1', owner_id='owner1', case_type='mother',
            case_name='mother', date_modified=datetime.utcnow(),
            domain='domain-1',
        )

        child_case_id = uuid.uuid4().hex
        form, cases = _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', mother_case_id)
            },
            domain='domain-2',
        )
        self.assertEqual(0, len(cases))
        self.assertTrue(form.is_error)
        self.assertTrue('InvalidCaseIndex' in form.problem)

    def test_case_with_attachment(self):
        # same as update, attachments
        pass

    def test_date_opened_coercion(self):
        delete_all_users()
        clear_domain_names('some-domain')
        self.project = Domain(name='some-domain')
        self.project.save()
        self.addCleanup(self.project.delete)
        user = create_restore_user(self.project.name)
        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        case = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=user.user_id, owner_id=user.user_id, case_type='demo',
            case_name='create_case', date_modified=modified_on, date_opened=modified_on, update={
                'dynamic': '123'
            }
        )

        submit_case_blocks([case.as_text()], domain='some-domain')
        # update the date_opened to date type to check for value on restore
        case.date_opened = case.date_opened.date()
        deprecated_check_user_has_case(self, user, case.as_xml())

    @staticmethod
    def _submit_dummy_form(domain, user_id, device_id='', sync_log_id=None, form_id=None):
        form_id = form_id or uuid.uuid4().hex
        form = """
            <data xmlns="http://openrosa.org/formdesigner/blah">
                <meta>
                    <userID>{user_id}</userID>
                    <deviceID>{device_id}</deviceID>
                    <instanceID>{form_id}</instanceID>
                </meta>
            </data>
        """
        return submit_form_locally(
            form.format(user_id=user_id, device_id=device_id, form_id=form_id),
            domain,
            last_sync_token=sync_log_id,
        )

    def test_restore_caches_cleared(self):
        sync_log_id = 'a8cac9222f42480764d6875c908040d5'
        device_id = 'CBNMP7XCGTIIAPCIMNI2KRGY'
        restore_payload_path_cache = RestorePayloadPathCache(
            domain=DOMAIN,
            user_id='user_id',
            sync_log_id=sync_log_id,
            device_id=device_id,
        )
        restore_payload_path_cache.set_value('test-thing')
        self.assertEqual(restore_payload_path_cache.get_value(), 'test-thing')
        self._submit_dummy_form(
            domain=DOMAIN,
            user_id='user_id',
            device_id=device_id,
            sync_log_id=sync_log_id,
        )
        self.assertIsNone(restore_payload_path_cache.get_value())

    def test_update_case_without_creating_triggers_soft_assert(self):
        def _submit_form_with_cc_version(version):
            xml = """<?xml version='1.0' ?>
                <system version="1" uiVersion="1"
                        xmlns="http://commcarehq.org/case"
                        xmlns:orx="http://openrosa.org/jr/xforms">
                    <orx:meta xmlns:cc="http://commcarehq.org/xforms">
                        <orx:deviceID />
                        <orx:timeStart>2017-06-22T08:39:07.585584Z</orx:timeStart>
                        <orx:timeEnd>2017-06-22T08:39:07.585584Z</orx:timeEnd>
                        <orx:username>system</orx:username>
                        <orx:userID></orx:userID>
                        <orx:instanceID>{form_id}</orx:instanceID>
                        <cc:appVersion>CommCare Version "{version}"</cc:appVersion>
                    </orx:meta>
                    <case case_id="{case_id}"
                            date_modified="2017-06-22T08:39:07.585427Z"
                            user_id="user2"
                            xmlns="http://commcarehq.org/case/transaction/v2" />
                </system>
            """.format(
                form_id=uuid.uuid4().hex,
                case_id=uuid.uuid4().hex,
                version=version,
            )
            submit_form_locally(
                xml, domain=DOMAIN
            )
        with self.assertRaisesMessage(AssertionError, 'Case created without create block in CC version >= 2.44'):
            _submit_form_with_cc_version("2.44")

        with self.assertRaisesMessage(AssertionError, 'Case created without create block'):
            _submit_form_with_cc_version("2.43")

    def test_duplicate_with_attachment(self):
        def main():
            attachments = {
                'pic.jpg': UploadedFile(BytesIO(b"fake"), 'pic.jpg', content_type='image/jpeg', size=4)
            }
            form_id = uuid.uuid4().hex
            form = get_simple_form_xml(form_id)

            form_1 = submit_and_fetch(form, DOMAIN, attachments)
            self.assertTrue(not form_1.is_duplicate)
            check_attachments(form_1, attachments)

            form_2 = submit_and_fetch(form, DOMAIN, attachments)
            form_1 = self.formdb.get_form(form_id)
            self.assertTrue(not form_1.is_duplicate)
            self.assertTrue(form_2.is_duplicate)
            check_attachments(form_1, attachments)
            check_attachments(form_2, attachments)

        def submit_and_fetch(form, domain, attachments):
            result = submit_form_locally(form, domain, attachments=attachments)
            return self.formdb.get_form(result.xform.form_id)

        def check_attachments(form, attachments):
            self.assertEqual(form.attachments.keys(), attachments.keys())

        main()

    def test_long_value_validation(self):
        case_id = uuid.uuid4().hex
        case = CaseBlock(
            create=True,
            case_id=case_id,
            user_id='user1',
            owner_id='user1',
            case_type='demo',
            case_name='this is a very long case name that exceeds the 255 char limit' * 5
        )

        xform, cases = submit_case_blocks([case.as_text()], domain=DOMAIN)
        self.assertEqual(0, len(cases))
        self.assertTrue(xform.is_error)
        self.assertIn('CaseValueError', xform.problem)

    def test_caching_form_attachment_during_submission(self):
        with patch.object(get_blob_db(), 'get', side_effect=Exception('unexpected blobdb read')):
            _submit_case_block(True, uuid.uuid4().hex, user_id='user2', update={})


@flag_enabled('SYNC_SEARCH_CASE_CLAIM')
@patch('corehq.motech.repeaters.models.domain_has_privilege', lambda x, y: True)
@es_test(requires=[case_search_adapter])
class CaseSearchTests(FundamentalBaseTests):
    def setUp(self):
        CaseSearchConfig(
            domain=DOMAIN,
            enabled=True,
            synchronous_web_apps=True,
        ).save()

    @patch.object(CouchUser, 'get_by_user_id', return_value=None)
    def test_create_case_and_update_elasticsearch(self, user_mock):
        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        xmlns = 'http://commcare.org/test_xmlns'
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=modified_on, date_opened=modified_on, update={
                'dynamic': '123'
            },
            device_id=FORMPLAYER_DEVICE_ID,
            xmlns=xmlns
        )
        # This case is sent to elasticsearch synchronously, without pillowtop
        manager.index_refresh(case_search_adapter.index_name)
        es_case = case_search_adapter.get(case_id)
        case_props = {prop['key']: prop['value'] for prop in es_case['case_properties']}
        self.assertEqual(case_props['dynamic'], '123')


def _submit_case_block(create, case_id, xmlns=SYSTEM_FORM_XMLNS, device_id=None, **kwargs):
    domain = kwargs.pop('domain', DOMAIN)
    return submit_case_blocks(
        [
            CaseBlock(
                create=create,
                case_id=case_id,
                **kwargs
            ).as_text()
        ],
        domain=domain,
        device_id=device_id,
        xmlns=xmlns,
    )


class IteratorTests(TestCase):
    def test_iterator(self):
        i = XFormQuestionValueIterator("/data/a-group/repeat_group[2]/question_id")
        self.assertIsNone(i.last())
        self.assertEqual(next(i), ('a-group', None))
        self.assertEqual(next(i), ('repeat_group', 1))
        with self.assertRaises(StopIteration):
            next(i)
        self.assertEqual(i.last(), 'question_id')
