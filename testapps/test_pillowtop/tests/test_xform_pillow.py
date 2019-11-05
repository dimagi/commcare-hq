from decimal import Decimal

from django.test import override_settings
from django.test.testcases import SimpleTestCase, TestCase

from couchdbkit import ResourceConflict
from mock import patch

from dimagi.utils.parsing import string_to_utc_datetime
from pillow_retry.models import PillowError
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.es import FormES
from corehq.apps.users.models import CommCareUser, UserReportingMetadataStaging
from corehq.apps.users.tasks import process_reporting_metadata_staging
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    run_with_all_backends,
)
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.es.elasticsearch import ConnectionError
from corehq.util.test_utils import get_form_ready_to_save, trap_extra_setup
from testapps.test_pillowtop.utils import process_pillow_changes


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
            cls.password
        )
        cls.metadata = TestFormMetadata(
            domain=cls.domain,
            user_id=cls.user._id,
        )

    def setUp(self):
        super().setUp()
        FormProcessorTestUtils.delete_all_xforms()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            initialize_index_and_mapping(self.elasticsearch, XFORM_INDEX_INFO)
        delete_es_index(XFORM_INDEX_INFO.index)

    def tearDown(self):
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        user = CommCareUser.get_by_user_id(self.user._id, self.domain)
        user.reporting_metadata.last_submissions = []
        user.save()
        PillowError.objects.all().delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        super().tearDownClass()

    @run_with_all_backends
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

    @run_with_all_backends
    def test_form_soft_deletion(self):
        form, metadata = self._create_form_and_sync_to_es()

        # verify there
        results = FormES().run()
        self.assertEqual(1, results.total)

        # soft delete the form
        with self.process_form_changes:
            FormAccessors(self.domain).soft_delete_forms([form.form_id])
        self.elasticsearch.indices.refresh(XFORM_INDEX_INFO.index)

        # ensure not there anymore
        results = FormES().run()
        self.assertEqual(0, results.total)

    @run_with_all_backends
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

    @run_with_all_backends
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

    @run_with_all_backends
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
            form = get_form_ready_to_save(self.metadata, is_db_test=True)
            form_processor = FormProcessorInterface(domain=self.domain)
            form_processor.save_processed_models([form])
        self.elasticsearch.indices.refresh(XFORM_INDEX_INFO.index)
        return form, self.metadata


class TransformXformForESTest(SimpleTestCase):
    def test_transform_xform_for_elasticsearch_app_versions(self):
        doc_dict = {
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'appVersion': 'version "2.27.2"(414569). App v56. 2.27. Build 414569'
                }
            }
        }
        doc_ret = transform_xform_for_elasticsearch(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['commcare_version'], '2.27.2')
        self.assertEqual(doc_ret['form']['meta']['app_build_version'], 56)

    def test_transform_xform_for_elasticsearch_app_versions_none(self):
        doc_dict = {
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'appVersion': 'not an app version'
                }
            }
        }
        doc_ret = transform_xform_for_elasticsearch(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['commcare_version'], None)
        self.assertEqual(doc_ret['form']['meta']['app_build_version'], None)

    def test_transform_xform_for_elasticsearch_location(self):
        doc_dict = {
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'location': '42.7 -21 0 0'
                }
            }
        }
        doc_ret = transform_xform_for_elasticsearch(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['geo_point'], {'lat': Decimal('42.7'), 'lon': Decimal('-21')})

    def test_transform_xform_for_elasticsearch_location_missing(self):
        doc_dict = {
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                }
            }
        }
        doc_ret = transform_xform_for_elasticsearch(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['geo_point'], None)

    def test_transform_xform_for_elasticsearch_location_bad(self):
        doc_dict = {
            'domain': 'demo',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'meta': {
                    'location': 'not valid'
                }
            }
        }
        doc_ret = transform_xform_for_elasticsearch(doc_dict)
        self.assertEqual(doc_ret['form']['meta']['geo_point'], None)

    def test_transform_xform_base_case_dates(self):
        doc_dict = {
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
        doc_ret = transform_xform_for_elasticsearch(doc_dict)
        self.assertIsNotNone(doc_ret)

    def test_transform_xform_base_case_xmlns(self):
        doc_dict = {
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
        doc_ret = transform_xform_for_elasticsearch(doc_dict)
        self.assertIsNotNone(doc_ret)
