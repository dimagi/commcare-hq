from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
from domain.models import Domain
from hq.models import Organization, ReporterProfile
from hq.tests.util import create_user_and_domain
from reporters.models import Reporter

class ViewsTestCase(TestCase):
    def setUp(self):
        user, domain = create_user_and_domain()
        self.client.login(username='brian',password='test')
        org = Organization(name='mockorg', domain=domain)
        org.save()            

    def testBasicViews(self):
        reporter = Reporter(alias="rapporteur")
        reporter.save()
        domain = Domain.objects.get(name='mockdomain')
        profile = ReporterProfile(reporter=reporter, domain=domain)
        profile.save()

        response = self.client.get('/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/serverup.txt')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/change_password/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/reporters/add/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        response = self.client.get('/reporters/%s/' % reporter.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/charts/default/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/charts/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/stats/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        # TODO - fix
        """
        response = self.client.get('/stats/delinquents/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        """
        # format url variables like so: 
        # response = self.client.get('/api/xforms/',{'format':'json'})

    def tearDown(self):
        user = User.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
