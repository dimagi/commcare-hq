from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
from hq.tests.util import create_user_and_domain
from domain.models import Domain
from graphing.models import *


class ViewsTestCase(TestCase):
    
    def setUp(self):
        create_user_and_domain()
        self.client.login(username='brian',password='test')

    def testBasicViews(self):
        # TODO - fix
        # table_name = ?
        graph = RawGraph.objects.all()[0]
        group = GraphGroup.objects.all()[0]
        
        # TODO - fix
        """
        response = self.client.get('/inspector/%s/' % table_name)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        """

        response = self.client.get('/showgraph/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/showgraph/%s/' % graph.id)
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/showgraph/all/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)

        response = self.client.get('/chartgroups/')
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        response = self.client.get('/chartgroups/%s/' % (group.id))
        self.assertNotContains(response,"Error", status_code=200)
        self.assertNotContains(response,"Exception", status_code=200)
        
        # format url variables like so: 
        # response = self.client.get('/api/xforms/',{'format':'json'})

    def tearDown(self):
        user = User.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name='mockdomain')
        domain.delete()
