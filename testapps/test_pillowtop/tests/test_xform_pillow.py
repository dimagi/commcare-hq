from datetime import datetime
from unittest.mock import patch

from django.test import override_settings
from django.test.testcases import SimpleTestCase, TestCase

from couchdbkit import ResourceConflict

from dimagi.utils.parsing import string_to_utc_datetime
from pillow_retry.models import PillowError

from corehq.apps.es import FormES
from corehq.apps.es.client import manager
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import CommCareUser, UserReportingMetadataStaging
from corehq.apps.users.tasks import process_reporting_metadata_staging
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import get_form_ready_to_save
from testapps.test_pillowtop.utils import process_pillow_changes


@es_test(requires=[form_adapter])
class XFormPillowTest(TestCase):
    domain = 'xform-pillowtest-domain'
    username = 'xform-pillowtest-user'
    password = 'badpassword'
    pillow_id = 'xform-pillow'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process_form_changes = process_pillow_changes('DefaultChangeFeedPillow')
        cls.process_form_changes.add_pillow(cls.pillow_id, {'skip_ucr': True})
        cls.user = CommCareUser.create(
            cls.domain,
            cls.username,
            cls.password,
            None,
            None,
        )
        cls.metadata = TestFormMetadata(
            domain=cls.domain,
            user_id=cls.user._id,
        )

    def setUp(self):
        super().setUp()
        FormProcessorTestUtils.delete_all_xforms()

    def tearDown(self):
        user = CommCareUser.get_by_user_id(self.user._id, self.domain)
        user.reporting_metadata.last_submissions = []
        user.save()
        PillowError.objects.all().delete()
        UserReportingMetadataStaging.objects.all().delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        super().tearDownClass()

    def test_xform_pillow(self):
        form, metadata = self._create_form_and_sync_to_es()

        # confirm change made it to elasticserach
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(form.form_id, form_doc['_id'])
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])

    def test_form_soft_deletion(self):
        form, metadata = self._create_form_and_sync_to_es()

        # verify there
        results = FormES().run()
        self.assertEqual(1, results.total)

        # soft delete the form
        with self.process_form_changes:
            XFormInstance.objects.soft_delete_forms(self.domain, [form.form_id])
        manager.index_refresh(form_adapter.index_name)

        # ensure not there anymore
        results = FormES().run()
        self.assertEqual(0, results.total)

    def test_form_hard_deletion(self):
        form, metadata = self._create_form_and_sync_to_es()

        # verify there
        results = FormES().run()
        self.assertEqual(1, results.total)

        # soft delete the form
        with self.process_form_changes:
            XFormInstance.objects.hard_delete_forms(self.domain, [form.form_id])
        manager.index_refresh(form_adapter.index_name)

        # ensure not there anymore
        results = FormES().run()
        self.assertEqual(0, results.total)

    @override_settings(USER_REPORTING_METADATA_BATCH_ENABLED=False)
    def test_app_metadata_tracker_non_batch(self):
        form, metadata = self._create_form_and_sync_to_es()
        user = CommCareUser.get_by_user_id(self.user._id, self.domain)
        self.assertEqual(len(user.reporting_metadata.last_submissions), 1)
        last_submission = user.reporting_metadata.last_submissions[0]

        self.assertEqual(
            last_submission.submission_date,
            string_to_utc_datetime(self.metadata.received_on),
        )
        self.assertEqual(last_submission.app_id, self.metadata.app_id)

    @override_settings(USER_REPORTING_METADATA_BATCH_ENABLED=True)
    def test_app_metadata_tracker(self):
        form, metadata = self._create_form_and_sync_to_es()
        self.assertEqual(UserReportingMetadataStaging.objects.count(), 1)
        self.assertEqual(UserReportingMetadataStaging.objects.first().user_id, self.user._id)

        # Test two forms before updating
        form, metadata = self._create_form_and_sync_to_es()
        self.assertEqual(UserReportingMetadataStaging.objects.count(), 1)
        self.assertEqual(UserReportingMetadataStaging.objects.first().user_id, self.user._id)
        self.assertEqual(0, PillowError.objects.filter(pillow=self.pillow_id).count())

        process_reporting_metadata_staging()
        self.assertEqual(UserReportingMetadataStaging.objects.count(), 0)
        user = CommCareUser.get_by_user_id(self.user._id, self.domain)
        self.assertEqual(len(user.reporting_metadata.last_submissions), 1)
        last_submission = user.reporting_metadata.last_submissions[0]

        self.assertEqual(
            last_submission.submission_date,
            string_to_utc_datetime(self.metadata.received_on),
        )
        self.assertEqual(last_submission.app_id, self.metadata.app_id)

    @override_settings(USER_REPORTING_METADATA_BATCH_ENABLED=True)
    def test_app_metadata_tracker_synclog_processed(self):
        UserReportingMetadataStaging.add_sync(
            self.domain, self.user._id, self.metadata.app_id,
            '123', datetime.utcnow(), self.metadata.device_id
        )

        form, metadata = self._create_form_and_sync_to_es()
        self.assertEqual(UserReportingMetadataStaging.objects.count(), 1)
        self.assertEqual(UserReportingMetadataStaging.objects.first().user_id, self.user._id)

        process_reporting_metadata_staging()
        self.assertEqual(UserReportingMetadataStaging.objects.count(), 0)
        user = CommCareUser.get_by_user_id(self.user._id, self.domain)
        self.assertEqual(len(user.reporting_metadata.last_submissions), 1)
        last_submission = user.reporting_metadata.last_submissions[0]

        self.assertEqual(
            last_submission.submission_date,
            string_to_utc_datetime(self.metadata.received_on),
        )
        self.assertEqual(last_submission.app_id, self.metadata.app_id)

    def _test_heartbeat(self, num_submissions):
        sync_date = datetime.utcnow()
        UserReportingMetadataStaging.add_heartbeat(
            self.domain, self.user._id, self.metadata.app_id,
            '123', sync_date, 'heartbeat_device_id',
            230, 2, 10, 'CommCare 2.28', 'en', 'acegi'
        )

        self.assertEqual(UserReportingMetadataStaging.objects.count(), 1)
        self.assertEqual(UserReportingMetadataStaging.objects.first().user_id, self.user._id)

        process_reporting_metadata_staging()
        self.assertEqual(UserReportingMetadataStaging.objects.count(), 0)
        ccuser = CommCareUser.get_by_user_id(self.user._id, self.domain)

        self.assertEqual(len(ccuser.reporting_metadata.last_submissions), num_submissions)
        self.assertEqual(len(ccuser.reporting_metadata.last_syncs), 1)
        self.assertEqual(ccuser.reporting_metadata.last_syncs[0].sync_date, sync_date)
        self.assertEqual(ccuser.reporting_metadata.last_sync_for_user.sync_date, sync_date)
        self.assertEqual(ccuser.last_device.device_id, 'heartbeat_device_id')
        self.assertEqual(ccuser.last_device.fcm_token, 'acegi')
        app_meta = ccuser.last_device.get_last_used_app_meta()
        self.assertEqual(app_meta.num_unsent_forms, 2)
        self.assertEqual(app_meta.num_quarantined_forms, 10)

    @override_settings(USER_REPORTING_METADATA_BATCH_ENABLED=True)
    def test_app_metadata_tracker_heartbeat_processed(self):
        self._test_heartbeat(0)

    @override_settings(USER_REPORTING_METADATA_BATCH_ENABLED=True)
    def test_app_metadata_tracker_heartbeat_processed_with_sync_prior(self):
        UserReportingMetadataStaging.add_sync(
            self.domain, self.user._id, self.metadata.app_id,
            '123', datetime.utcnow(), self.metadata.device_id
        )
        form, metadata = self._create_form_and_sync_to_es()
        # existing row should get updated, no new row should be added
        self._test_heartbeat(1)

    def test_form_pillow_error_in_form_metadata(self):
        self.assertEqual(0, PillowError.objects.filter(pillow=self.pillow_id).count())
        with patch('pillowtop.processors.form.mark_latest_submission') as mark_latest_submission:
            mark_latest_submission.side_effect = ResourceConflict('couch sucks')
            case_id, case_name = self._create_form_and_sync_to_es()

        # confirm change made it to form index
        results = FormES().run()
        self.assertEqual(1, results.total)

        self.assertEqual(1, PillowError.objects.filter(pillow=self.pillow_id).count())

    def _create_form_and_sync_to_es(self):
        with self.process_form_changes:
            form = self._create_form()
        manager.index_refresh(form_adapter.index_name)
        return form, self.metadata

    def _create_form(self):
        form = get_form_ready_to_save(self.metadata, is_db_test=True)
        form_processor = FormProcessorInterface(domain=self.domain)
        form_processor.save_processed_models([form])
        return form


class TransformXformForESTest(SimpleTestCase):
    def test_transform_xform_for_elasticsearch_app_versions(self):
        doc_dict = {
            '_id': 1,
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'appVersion': 'version "2.27.2"(414569). App v56. 2.27. Build 414569'
                }
            }
        }
        doc_ret = form_adapter.to_json(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['commcare_version'], '2.27.2')
        self.assertEqual(doc_ret['form']['meta']['app_build_version'], 56)

    def test_transform_xform_for_elasticsearch_app_versions_none(self):
        doc_dict = {
            '_id': 1,
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'appVersion': 'not an app version'
                }
            }
        }
        doc_ret = form_adapter.to_json(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['commcare_version'], None)
        self.assertEqual(doc_ret['form']['meta']['app_build_version'], None)

    def test_transform_xform_for_elasticsearch_location(self):
        doc_dict = {
            '_id': 1,
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'location': '42.7 -21 0 0'
                }
            }
        }
        doc_ret = form_adapter.to_json(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['geo_point'], {'lat': 42.7, 'lon': -21})

    def test_transform_xform_for_elasticsearch_location_missing(self):
        doc_dict = {
            '_id': 1,
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                }
            }
        }
        doc_ret = form_adapter.to_json(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['geo_point'], None)

    def test_transform_xform_for_elasticsearch_location_bad(self):
        doc_dict = {
            '_id': 1,
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'location': 'not valid'
                }
            }
        }
        doc_ret = form_adapter.to_json(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['geo_point'], None)

    def test_transform_xform_base_case_dates(self):
        doc_dict = {
            '_id': 1,
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                "case": {
                    "@case_id": "123",
                    "@date_modified": "13:54Z",
                },
            }
        }
        # previously raised an error
        doc_ret = form_adapter.to_json(doc_dict)
        self.assertIsNotNone(doc_ret)

    def test_transform_xform_base_case_xmlns(self):
        doc_dict = {
            '_id': 1,
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                "case": {
                    "@case_id": "123",
                    "@xmlns": "ZZZ"
                },
            }
        }
        # previously raised an error
        doc_ret = form_adapter.to_json(doc_dict)
        self.assertIsNotNone(doc_ret)
