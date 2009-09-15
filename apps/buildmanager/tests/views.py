from django.test import TestCase
from django.test.client import Client
from buildmanager.models import Project
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
        project = Project.objects.all()[0]
        build = ProjectBuild.objects.all()[0]
        
        response = self.client.get('/projects/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/projects/%s/' % project.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/projects/%s/latest/' % project.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        # TODO - fix this
        """
        response = self.client.get('/projects/%s/latest/%s' % (formdef.id, filename))
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        """

        response = self.client.get('/builds/' % (formdef.id, instance.id))
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/builds/%s/release/' % (formdef.id, instsance.id))
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        # TODO - fix
        """
        response = self.client.get('/builds/%s/%s/%s' % project.id, build_number, filename)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        """

        response = self.client.get('/builds/show/%s/' % build.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/builds/new/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        # format url variables like so: 
        # response = self.client.get('/api/xforms/',{'format':'json'})

    def tearDown(self):
        user = ExtUser.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
