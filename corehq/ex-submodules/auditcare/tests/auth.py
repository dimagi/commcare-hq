from __future__ import absolute_import
from __future__ import unicode_literals
import time
from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.test.client import Client
from django.contrib.auth.models import User
from django.test import TestCase

from auditcare.models import AuditEvent, ModelActionAudit, AccessAudit
from auditcare import models
from auditcare.tests.testutils import delete_all, get_latest_access
from auditcare.utils import _thread_locals
from six.moves import range


class AuthenticationTestCase(TestCase):
    def setUp(self):
        super(AuthenticationTestCase, self).setUp()
        if hasattr(_thread_locals, 'user'):
            delattr(_thread_locals, 'user')
        User.objects.all().delete()
        delete_all(AuditEvent, 'auditcare/all_events')
        self.client = Client()
        self._createUser()

    def _createUser(self):
        model_count = ModelActionAudit.view("auditcare/model_actions_by_id", include_docs=True, reduce=False).count()
        total_count = AuditEvent.view("auditcare/all_events").count()
        
        usr = User()
        usr.username = 'mockmock@mockmock.com'
        usr.set_password('mockmock')
        usr.first_name='mocky'
        usr.last_name = 'mock'
        usr.save()

        model_count2 = ModelActionAudit.view("auditcare/model_actions_by_id", include_docs=True, reduce=False).count()
        total_count2 = AuditEvent.view("auditcare/all_events").count()
        
        self.assertEqual(model_count+1, model_count2)    
        self.assertEqual(total_count+1, total_count2)
    
    def testModifyUser(self):
        model_count = ModelActionAudit.view("auditcare/model_actions_by_id", include_docs=True, reduce=False).count()
        total_count = AuditEvent.view("auditcare/all_events").count()
        
        usr = User.objects.get(username='mockmock@mockmock.com')
        usr.first_name='aklsjfl'
        time.sleep(1)
        usr.save()
        time.sleep(1)

        model_count2 = ModelActionAudit.view("auditcare/model_actions_by_id", include_docs=True, reduce=False).count()
        total_count2 = AuditEvent.view("auditcare/all_events").count()
                
        self.assertEqual(model_count+1, model_count2)    
        self.assertEqual(total_count+1, total_count2)
    
    
    def testLogin(self):

        #login
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        response = self.client.post(reverse('auth_login'), {'username': 'mockmock@mockmock.com', 'password': 'mockmock'})
        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count+1, login_count)

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(latest_audit.access_type, models.ACCESS_LOGIN)

        #django test client doesn't seem to like logout for some reason
        #logout
#        response = self.client.get('/accounts/logout')
#        logging.error(response.content)
#        #self.client.logout()
#        logout_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com'], include_docs=True).count()
#        self.assertEqual(start_count+2, logout_count)
        
        
    def testSingleFailedLogin(self):
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        response = self.client.post(reverse('auth_login'), {'username': 'mockmock@mockmock.com', 'password': 'wrongwrongwrong'})

        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEquals(start_count+1, login_count)
        #got the basic count, now let's inspect this value to see what kind of result it is.

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(latest_audit.access_type, models.ACCESS_FAILED)
        self.assertEquals(latest_audit.failures_since_start, 1)


    def testRepeatedFailedLogin(self):
        from auditcare.decorators import login
        login.FAILURE_LIMIT = 3
        login.LOCK_OUT_AT_FAILURE=True
        login.COOLOFF_TIME = timedelta(seconds=4)

        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        response = self.client.post(reverse('auth_login'), {'username': 'mockmock@mockmock.com', 'password': 'wrongwrongwrong'})

        firstlogin_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEquals(start_count+1, firstlogin_count)


        first_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(first_audit.access_type, models.ACCESS_FAILED)
        self.assertEquals(first_audit.failures_since_start, 1)
        start_failures = first_audit.failures_since_start

        for n in range(1, 3):
            #we are logging in within the cooloff period, so let's check to see if it doesn't increment.
            response = self.client.post(reverse('auth_login'), {'username': 'mockmock@mockmock.com', 'password': 'wrongwrongwrong'})
            next_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
            self.assertEquals(firstlogin_count, next_count)

            next_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
            self.assertEquals(next_audit.access_type, models.ACCESS_FAILED)
            self.assertEquals(next_audit.failures_since_start, n+start_failures)
            time.sleep(1)
        time.sleep(3)
        response = self.client.post(reverse('auth_login'), {'username': 'mockmock@mockmock.com', 'password': 'wrongwrong'})
        cooled_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(cooled_audit.failures_since_start, 1)
