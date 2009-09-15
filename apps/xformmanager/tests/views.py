from django.test import TestCase
from django.test.client import Client
from xformmanager.tests.util import create_xsd_and_populate, populate
from xformmanager.manager import XFormManager
from hq.models import ExtUser, Domain

class ViewsTestCase(TestCase):
    def setUp(self):
        domain = Domain(name='mockdomain')
        domain.save()
        user = ExtUser()
        user.domain = domain
        user.username = 'brian'
        user.password = 'sha1$245de$137d06d752eee1885a6bbd1e40cbe9150043dd5e'
        user.save()
        self.client.login(username='brian',password='test')

    def testBasicViews(self):
        domain = Domain.objects.get(name='mockdomain')
        formdef = create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml", domain)
        instance = populate("data/pf_followup_2.xml")

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

        response = self.client.get('/xforms/show/%s/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        response = self.client.get('/xforms/show/%s/%s/' % (formdef.id, instance.id))
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/show/%s/%s/csv/' % (formdef.id, instance.id))
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/data/%s/delete/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/data/%s/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/data/%s/csv/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/data/%s/xml/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/xforms/%s/submit/' % formdef.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        # format url variables like so: 
        # response = self.client.get('/api/xforms/',{'format':'json'})

        manager = XFormManager()
        manager.remove_schema(formdef.id)

    def tearDown(self):
        user = ExtUser.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
