from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
from xformmanager.tests.util import create_xsd_and_populate, populate
from xformmanager.manager import XFormManager
from domain.models import Domain
from hq.tests.util import create_user_and_domain

class ViewsTestCase(TestCase):
    
    def setUp(self):
        user, domain = create_user_and_domain(username='brian',password='test', domain_name='mockdomain')
        self.authuser = user
        self.authuser.password = 'test'
        self.client.login(username='brian',password='test')
        user, domain = create_user_and_domain(username='john',password='test', domain_name='seconddomain')
        self.unauthuser = user
        self.unauthuser.password = 'test'

    def testBasicViews(self):
        domain = Domain.objects.get(name='mockdomain')
        formdef = create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml", domain)
        instance = populate("data/pf_followup_2.xml", domain)

        response = self.client.get('/xforms/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/register/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/reregister/mockdomain/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/remove/%s/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/%s/submit/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        urls = [
            '/xforms/show/%s/' % formdef.id, 
            '/xforms/show/%s/%s/' % (formdef.id, instance.id), 
            '/xforms/show/%s/%s/csv/' % (formdef.id, instance.id), 
            '/xforms/data/%s/delete/' % formdef.id, 
            '/xforms/data/%s/' % formdef.id, 
            '/xforms/data/%s/csv/' % formdef.id, 
            '/xforms/data/%s/xml/' % formdef.id, 
        ]
        
        for url in urls:
            self._test_valid_and_permissions(url, self.authuser, self.unauthuser)

        # format url variables like so: 
        # response = self.client.get('/api/xforms/',{'format':'json'})

        manager = XFormManager()
        manager.remove_schema(formdef.id)

    def tearDown(self):
        user = User.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
        
    def _test_valid_and_permissions(self, url, authuser, unauthuser):
        """ TODO - move this to hq.tests.util """
        self._test_valid_url(url)
        self._test_permissions(unauthuser, url, 302, authuser)

    def _test_valid_url(self, url):
        """ 
        TODO - move this to hq.tests.util
        
        """
        response = self.client.get(url)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
    
    def _test_permissions(self, test_as, url, status_code, return_as, 
                         contains=None, not_contains=None):
        """
        TODO - move this to hq.tests.util

        This function logs in the user provided by 'test_as',
        hits the view specified by 'url'
        checks for status code 'status_code'
        logs in the user provided by 'return_as'
        and returns
        """
        self.client.logout()
        self.client.login(username=test_as.username,password=test_as.password)
        response = self.client.get(url)
        if contains is not None:
            self.assertContains(response, contains, status_code=status_code)
        if not_contains is not None:
            self.assertNotContains(response, not_contains, status_code=status_code)
        if contains is None and not_contains is None:
            self.assertContains(response, '', status_code=status_code)
        self.client.logout()
        self.client.login(username=return_as.username ,password=return_as.password)
