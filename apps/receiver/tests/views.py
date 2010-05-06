from django.test import TestCase
from django.test.client import Client
from domain.models import Domain
from django.contrib.auth.models import User
from hq.tests.util import create_user_and_domain
from receiver.tests.util import *

class ViewsTestCase(TestCase):
    
    def setUp(self):
        create_user_and_domain()
        self.client.login(username='brian',password='test')

    def testBasicViews(self):
        domain = Domain.objects.get(name='mockdomain')
        submission = makeNewEntry(get_full_path('simple-meta.txt'),
                                  get_full_path('simple-body.txt'))
        
        response = self.client.get('/receiver/submit/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/submit/%s' % domain.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/resubmit/%s/' % domain.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/review/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/review/%s/delete' % submission.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/review/%s' % submission.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/attachment/%s/' % submission.xform.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/orphaned_data/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/receiver/orphaned_data/xml/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        # format url variables like so: 
        # response = self.client.get('/api/xforms/',{'format':'json'})
        
        submission.delete()

    def tearDown(self):
        user = User.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
