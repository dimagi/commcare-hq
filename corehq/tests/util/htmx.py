from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser


class HtmxViewTestCase(TestCase):
    domain = 'htmx-view-test'
    username = 'username@test.com'

    def get_url(self):
        raise NotImplementedError()

    @classmethod
    def setUpTestData(cls):
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(
            cls.domain, cls.username, 'password', None, None, is_admin=True
        )
        cls.addClassCleanup(cls.user.delete, cls.domain, None)

    def hx_action(self, action, data):
        """Call an HTMX view action (the view method decorated with @hq_hx_action) and receive the response"""
        self.client.login(username=self.username, password='password')
        return self.client.post(self.get_url(), data, headers={'HQ-HX-Action': action})
