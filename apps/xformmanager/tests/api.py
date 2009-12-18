from django.test import TestCase
from django.test.client import Client
from xformmanager.tests.util import create_xsd_and_populate, clear_data
from xformmanager.models import *
from xformmanager.manager import XFormManager
from hq.models import ExtUser
from hq.tests.util import create_user_and_domain

class APITestCase(TestCase):
    
    def setUp(self):
        # we cannot load this using django built-in fixtures
        # because django filters are model dependent
        # (and we have a whack of dynamically generated non-model db tables)
        clear_data()
        user, domain = create_user_and_domain()
        create_xsd_and_populate("data/brac_chw.xsd", "data/brac_chw_1.xml", domain)
        self.client.login(username='brian',password='test')

    def test_api_calls(self):
        # test the actual URL plus the non APPEND_SLASH url
        # (django should return 301 - permanently moved)
        response = self.client.get('/api')
        self.assertStatus(response, 301)
        response = self.client.get('/api/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms')
        self.assertStatus(response, 301)
        response = self.client.get('/api/xforms/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1')
        self.assertStatus(response, 301)
        response = self.client.get('/api/xforms/1/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/1')
        self.assertStatus(response, 301)
        response = self.client.get('/api/xforms/1/1/')
        self.assertStatus(response, 200)
        
        # because the URLs do not end in '$', then both 
        # of these URL pairs are caught by the same expression
        response = self.client.get('/api/xforms/1/schema')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/schema/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/metadata')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/metadata/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/1/metadata')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/1/metadata/')
        self.assertStatus(response, 200)

    def test_formats(self):
        # oddly enough, if the GET variables are passed incorrectly,
        # the unit tests fail on a TemplateSyntaxError. Why?
        response = self.client.get('/api/xforms/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/',{'format':'json'})
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/',{'format':'xml'})
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/',{'format':'xml'})
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/',{'format':'zip'})
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/1/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/1/',{'format':'xml'})
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/metadata/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/metadata/',{'format':'xml'})
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/1/metadata/')
        self.assertStatus(response, 200)
        response = self.client.get('/api/xforms/1/1/metadata/',{'format':'xml'})
        self.assertStatus(response, 200)
        
    # TODO - flesh this out properly once we've solidified our data format
    def test_api_contents_INCOMPLETE(self):
        response = self.client.get('/api/xforms/')
        self.assertContains(response,"schema_brac_chw_chwvisit_v0_0_1,", status_code=200)
        response = self.client.get('/api/xforms/',{'format':'json'})
        self.assertContains(response,"\"pk\": 1", status_code=200)

    def assertStatus(self, response, status):
        if response.status_code != status:
            print "ERROR :" + response.content    
        self.failUnlessEqual(response.status_code, status)

    def tearDown(self):
        manager = XFormManager()
        manager.remove_schema(1)


