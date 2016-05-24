from django.test import TestCase
from elasticsearch.exceptions import ConnectionError
from mock import Mock

from corehq.apps.reports.util import create_export_filter
from corehq.apps.users.models import CommCareUser
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from corehq.pillows.xform import XFormPillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup


DOMAIN = 'test_domain'


class ReportUtilTests(TestCase):
    pillow_class = XFormPillow
    es_index = XFORM_INDEX

    def setUp(self):
        self.user = CommCareUser.create(DOMAIN, 'user1', '***')
        self.request = Mock()
        self.request.method = 'POST'
        self.request.POST = {}
        self.request.project.commtrack_enabled = False
        self.request.couch_user = self.user.user_id

        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(self.es_index)
            self.pillow = self.get_pillow()

    def tearDown(self):
        ensure_index_deleted(self.es_index)
        self.user.delete()

    def get_pillow(self):
        return self.pillow_class()

    def test_create_export_form_filter(self):
        filter_ = create_export_filter(self.request, DOMAIN, export_type='form')
        self.assertEqual(
            filter_.dumps(),
            '[{"function": "corehq.apps.reports.util.app_export_filter", "kwargs": {"app_id": null}},'
            ' {"function": "corehq.apps.reports.util.datespan_export_filter", "kwargs": {"datespan": null}},'
            ' {"function": "corehq.apps.reports.util.users_filter", "kwargs": {"users": ["' +
            self.user.user_id + '"]}}]')

    def test_create_export_case_filter(self):
        filter_ = create_export_filter(self.request, DOMAIN, export_type='case')
        self.assertEqual(
            filter_.dumps(),
            '[{"function": "corehq.apps.reports.util.case_users_filter", "kwargs": {"users": ["' +
            self.user.user_id + '"], "groups": []}}]')
