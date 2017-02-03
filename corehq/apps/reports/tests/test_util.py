# coding: utf-8
from django.test import TestCase
from elasticsearch.exceptions import ConnectionError
from mock import Mock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.util import create_export_filter
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping

DOMAIN = 'test_domain'


class ReportUtilTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ReportUtilTests, cls).setUpClass()
        create_domain(DOMAIN)

    def setUp(self):
        super(ReportUtilTests, self).setUp()
        self.user = CommCareUser.create(DOMAIN, 'user1', '***')
        self.request = Mock()
        self.request.method = 'POST'
        self.request.POST = {}
        self.request.project.commtrack_enabled = False
        self.request.couch_user = self.user.user_id

        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(XFORM_INDEX_INFO.index)
            initialize_index_and_mapping(get_es_new(), XFORM_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        self.user.delete()
        super(ReportUtilTests, self).tearDown()

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
