import hashlib
import logging
from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
from domain.models import Domain
from hq.models import Organization, ReporterProfile
from hq.tests.util import create_user_and_domain
from receiver.models import Submission
from reporters.models import Reporter

class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.domain_name = 'mockdomain'
        self.username = 'brian'
        self.password = 'test'
        user, domain = create_user_and_domain(username = self.username,
                                              password = self.password, 
                                              domain_name=self.domain_name)
        # we are explicitly testing non-traditionally logged-in authentication
        # self.client.login(username=self.username,password=self.password)
        org = Organization(name='mockorg', domain=domain)
        org.save()

    def testBasicAuth(self):
        """This is a really junky way to submit a RAW text/xml submission via the client test API        
        but it works to test the header based authentication"""
        logging.error("THIS TEST (testBasicAuth) NEEDS TO BE FIXED.  YOU HAVE COMMENTED IT OUT AND NEED TO GO BACK AND DO SOMETHING ABOUT IT!")
        return 
        password_hash = hashlib.sha1(self.username + ":" + self.password).hexdigest()
        authorization = "HQ username=\"%s\", password=\"%s\"" % (self.username, password_hash)
        xformstr = '<?xml version="1.0" ?><geotagger id="geo_tagger"><timestamp>2009-10-28T13:45:07.512</timestamp><device_id>358279013739816</device_id></geotagger>'
        response = self.client.post('/receiver/submit/%s' % self.domain_name, 
                                    xformstr,
                                    content_type='text/xml',
                                    HTTP_AUTHORIZATION=authorization, 
                                    )
        submit = Submission.objects.latest()
        self.assertTrue(submit.authenticated_to!=None)

    def tearDown(self):
        user = User.objects.get(username='brian')
        user.delete()
        domain = Domain.objects.get(name=self.domain_name)
        domain.delete()
