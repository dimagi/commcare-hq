import os

from django.test import TestCase
from django.test.client import Client

from domain.models import Domain
from django.contrib.auth.models import User
from buildmanager.models import Project, ProjectBuild, BuildDownload
from buildmanager.tests.util import setup_build_objects 
from datetime import datetime

class ViewsTestCase(TestCase):
    
    def setUp(self):
        domain, user, project, build = setup_build_objects()
        self.domain = domain
        self.user = user
        self.project = project
        self.build = build
        self.client.login(username='brian',password='test')

    def testDownloadCount(self):
        # really basic test, hit the jad, check the counts, hit the jar, check the counts
        self.assertEquals(0, len(BuildDownload.objects.all()))
        self.assertEquals(0, len(self.build.downloads.all()))
        self.assertEquals(0, len(self.project.downloads.all()))
        response = self.client.get('/projects/%s/latest/%s' % (self.project.id, "dummy.jar"))
        self.assertEquals(1, len(BuildDownload.objects.all()))
        self.assertEquals(1, len(self.build.downloads.all()))
        self.assertEquals(1, len(self.project.downloads.all()))
        response = self.client.get('/projects/%s/latest/%s' % (self.project.id, "dummy.jad"))
        self.assertEquals(2, len(BuildDownload.objects.all()))
        self.assertEquals(2, len(self.build.downloads.all()))
        self.assertEquals(2, len(self.project.downloads.all()))
        
        self.assertEquals(1, len(BuildDownload.objects.filter(type="jad")))
        self.assertEquals(1, len(BuildDownload.objects.filter(type="jar")))
        
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

        response = self.client.get('/builds/')
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


    def tearDown(self):
        user = User.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
