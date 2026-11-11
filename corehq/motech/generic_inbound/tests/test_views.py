from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.users.models import WebUser
from corehq.motech.generic_inbound.models import ConfigurableAPI, RequestLog
from corehq.util.test_utils import flag_enabled


@flag_enabled('GENERIC_INBOUND_API')
class TestRequestLogActionViews(TestCase):
    domain = 'test-generic-inbound-log-actions'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)
        cls.addClassCleanup(cls.project.delete)
        cls.admin = WebUser.create(cls.domain, 'inbound-admin', 'password', None, None, is_admin=True)
        cls.addClassCleanup(cls.admin.delete, cls.domain, deleted_by=None)
        expression = UCRExpression.objects.create(
            name='expr', domain=cls.domain, expression_type=UCR_NAMED_EXPRESSION, definition={})
        cls.api = ConfigurableAPI.objects.create(domain=cls.domain, transform_expression=expression)

    def setUp(self):
        self.log = RequestLog.objects.create(
            domain=self.domain,
            api=self.api,
            status=RequestLog.Status.SUCCESS,
            response_status=200,
            username='someone',
            request_method=RequestLog.RequestMethod.POST,
            request_query='',
            request_body='{}',
            request_ip='127.0.0.1',
        )
        self.client.login(username='inbound-admin', password='password')

    def _url(self, urlname):
        return reverse(urlname, args=[self.domain, self.log.id])

    def test_revert_get_is_rejected(self):
        response = self.client.get(self._url('revert_api_request'))
        assert response.status_code == 405
        self.log.refresh_from_db()
        assert self.log.status == RequestLog.Status.SUCCESS

    def test_revert_post(self):
        response = self.client.post(self._url('revert_api_request'))
        assert response.status_code == 302
        self.log.refresh_from_db()
        assert self.log.status == RequestLog.Status.REVERTED

    @patch('corehq.motech.generic_inbound.views.reprocess_api_request')
    def test_retry_get_is_rejected(self, reprocess):
        response = self.client.get(self._url('retry_api_request'))
        assert response.status_code == 405
        reprocess.assert_not_called()

    @patch('corehq.motech.generic_inbound.views.reprocess_api_request')
    def test_retry_post(self, reprocess):
        response = self.client.post(self._url('retry_api_request'))
        assert response.status_code == 302
        reprocess.assert_called_once_with(self.log)
