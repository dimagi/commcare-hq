from django.test import TestCase
from django.test.client import Client
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
        # TODO: fix
        # case = ?

        response = self.client.get('/reports/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        # TODO - fix
        """
        response = self.client.get('/reports/%s/custom/%s' % (domain.id, report_name))
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        """

        response = self.client.get('/reports/%s/flat/' % case.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/reports/%s/csv/' % case.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/reports/%s/single/%s/' % (case.id, instance.id) )
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
                
        # format url variables like so: 
        # response = self.client.get('/api/xforms/',{'format':'json'})

    def tearDown(self):
        user = ExtUser.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
