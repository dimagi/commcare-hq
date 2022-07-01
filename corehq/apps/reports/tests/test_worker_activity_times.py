from datetime import datetime, timedelta
from unittest.mock import patch
import uuid
from django.http.request import QueryDict
from django.test import TestCase
from django.test.client import RequestFactory
import pytz
from corehq.apps.reports.standard.monitoring import WorkerActivityTimes
from corehq.form_processor.models.forms import XFormInstance
from corehq.pillows.xform import transform_xform_for_elasticsearch
from dimagi.utils.dates import DateSpan

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.users.models import (
    CommCareUser,
    WebUser,
)
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX, XFORM_INDEX_INFO

from corehq.util.elastic import ensure_index_deleted


class TestWorkerActivityTimesReport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'worker-activity-time-test'
        cls.user = WebUser(username='test_activity_report@cchq.com', domains=[cls.domain])
        cls.request_factory = RequestFactory()

        cls.form_list = [XFormInstance(**{
            'form_id': str(uuid.uuid4()),
            'domain': cls.domain,
            'received_on': d,
            'xmlns': 'http://openrosa.org/formdesigner/E17E4FC5',
        }) for d in [datetime.now(), datetime.now() - timedelta(days=1)]]

        user_uuid = str(uuid.uuid4())
        dummy_user = {
            '_id': user_uuid,
            'domain': cls.domain,
            'username': 'mobile-worker',
            'password': 'Some secret Pass',
            'created_by': None,
            'created_via': None,
            'email': 'mobileworker@commcarehq.com',
            'is_active': True,
            'doc_type': 'CommcareUser'
        }
        cls.user_obj = CommCareUser(**dummy_user)
        cls.form_list = []
        cls.es = get_es_new()
        initialize_index_and_mapping(cls.es, XFORM_INDEX_INFO)
        cls._send_forms_to_es()

    def setUp(self):
        super().setUp()
        self.request = self.request_factory.get('')
        self.request.couch_user = self.user
        self.request.domain = self.domain
        self.request.can_access_all_locations = True

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(XFORM_INDEX)
        super().tearDownClass()

    @classmethod
    def _send_forms_to_es(cls):
        for form in cls.form_list:
            send_to_elasticsearch('forms', transform_xform_for_elasticsearch(form.to_json()))
        cls.es.indices.refresh(XFORM_INDEX_INFO.index)

    @patch('corehq.apps.reports.standard.monitoring._get_selected_users')
    @patch('corehq.apps.reports.generic.get_timezone')
    def test_activity_times_does_not_error(self, tz_patch, user_patch):
        user_patch.return_value = [self.user_obj]
        tz_patch.return_value = pytz.utc
        q_dict = QueryDict('', mutable=True)
        q_dict.update({
            'filterSet': 'true',
            'emw': 't__4',
            'form_unknown': 'yes',
            'form_unknown_xmlns': 'http://openrosa.org/formdesigner/E17E4FC5',
            'form_status': 'active',
            'form_app_id': '',
            'form_module': '',
            'form_xmlns': '',
            'show_advanced': 'on',
            'sub_time': ''
        })
        self.request.GET = q_dict
        self.request.datespan = DateSpan.since(7)
        data = WorkerActivityTimes(request=self.request, domain=self.domain).activity_times
        self.assertEqual(len(data), 0)
