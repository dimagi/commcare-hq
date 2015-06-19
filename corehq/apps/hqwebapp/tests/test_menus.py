from django.test.client import RequestFactory
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqwebapp.models import (
    DashboardTab,
    ApplicationsTab,
)
from corehq.apps.users.models import WebUser
from corehq.toggles import CUSTOM_MENU_BAR


class TestCustomTopMenu(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain_name = 'test-domain'
        cls.domain = create_domain(cls.domain_name)
        cls.web_user = WebUser.create(
            cls.domain_name,
            'test',
            'password',
            'test@domain.com',
        )
        cls.web_user.add_domain_membership(cls.domain_name)
        cls.request = RequestFactory().get('')
        setattr(cls.request, 'project', cls.domain)
        cls.url = 'urlname'

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()

    def tearDown(self):
        CUSTOM_MENU_BAR.set('domain:%s' % self.domain_name, False)

    def test_dashboard_is_invisible(self):
        tab = DashboardTab(
            self.request,
            self.url,
            domain=self.domain_name,
            project=self.domain,
            couch_user=self.web_user
        )
        #
        self.assertTrue(tab.is_viewable)

        CUSTOM_MENU_BAR.set('domain:%s' % self.domain_name, True)
        self.assertFalse(tab.is_viewable)

    def test_applications_is_invisible(self):
        tab = ApplicationsTab(
            self.request,
            self.url,
            domain=self.domain_name,
            project=self.domain,
            couch_user=self.web_user
        )
        #
        self.assertTrue(tab.is_viewable)

        CUSTOM_MENU_BAR.set('domain:%s' % self.domain_name, True)
        self.assertFalse(tab.is_viewable)
