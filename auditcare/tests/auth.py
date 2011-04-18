from datetime import timedelta
import time
from django.test.client import Client
from django.contrib.auth.models import User, AnonymousUser
from auditcare.models import AuditEvent, ModelActionAudit, AccessAudit
from auditcare.models import couchmodels
import unittest
import settings
from auditcare.utils import _thread_locals
import logging


def delete_all(couchmodel, view_name, key=None, startkey=None, endkey=None):
    """Helper function to help delete/clear documents from the database of a certain type.
    Will call the view function opon a given couchdbkit model you specify (couchmodel), on the given view.  It will do an include_docs on the view request
    to get the entire document, it must return the actual couchmodel instances for the view for this to work.

    After that, it'll iterate through all the elements to delete the items in the resultset.
    """
    params = {}
    if key != None:
        params['key'] = key
    if startkey != None and endkey != None:
        params['startkey'] = startkey
        params['endkey'] = endkey
    params['include_docs'] = True
    data = couchmodel.view(view_name, **params).all()
    total_rows = len(data)

    for dat in data:
        try:
            dat.delete()
        except:
            pass
    return total_rows


def get_latest_access(key):
    access_events = AccessAudit.view('auditcare/login_events', key=key, include_docs=True).all()
    access_events = sorted(access_events, key=lambda x: x.event_date, reverse=True)
    return access_events[0]


class authenticationTestCase(unittest.TestCase):
    def setUp(self):
        if hasattr(_thread_locals, 'user'):
            delattr(_thread_locals, 'user')
        User.objects.all().delete()
        delete_all(AuditEvent, 'auditcare/all_events')
        self.client = Client()
        self._createUser()
            
    def _createUser(self):
        model_count = ModelActionAudit.view("auditcare/model_actions").count()
        total_count = AuditEvent.view("auditcare/all_events").count()
        
        usr = User()
        usr.username = 'mockmock@mockmock.com'
        usr.set_password('mockmock')
        usr.first_name='mocky'
        usr.last_name = 'mock'
        usr.save()

        model_count2 = ModelActionAudit.view("auditcare/model_actions").count()
        total_count2 = AuditEvent.view("auditcare/all_events").count()
        
        self.assertEqual(model_count+1, model_count2)    
        self.assertEqual(total_count+1, total_count2)
    
    def testModifyUser(self):
        print "testModifyUser"
        model_count = ModelActionAudit.view("auditcare/model_actions").count()
        total_count = AuditEvent.view("auditcare/all_events").count()
        
        usr = User.objects.get(username='mockmock@mockmock.com')
        usr.first_name='aklsjfl'
        usr.save()
        
        model_count2 = ModelActionAudit.view("auditcare/model_actions").count()
        total_count2 = AuditEvent.view("auditcare/all_events").count()
                
        self.assertEqual(model_count+1, model_count2)    
        self.assertEqual(total_count+1, total_count2)
    
    
    def testLogin(self):
        print "testLogin"

        #login
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        response = self.client.post('/accounts/login/', {'username': 'mockmock@mockmock.com', 'password': 'mockmock'})
        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count+1, login_count)

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(latest_audit.access_type, couchmodels.ACCESS_LOGIN)

        #django test client doesn't seem to like logout for some reason
        #logout
#        response = self.client.get('/accounts/logout')
#        logging.error(response.content)
#        #self.client.logout()
#        logout_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com'], include_docs=True).count()
#        self.assertEqual(start_count+2, logout_count)
        
        
    def testSingleFailedLogin(self):
        print "testFailedLogin"
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        response = self.client.post('/accounts/login/', {'username': 'mockmock@mockmock.com', 'password': 'wrongwrongwrong'})

        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEquals(start_count+1, login_count)
        #got the basic count, now let's inspect this value to see what kind of result it is.

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(latest_audit.access_type, couchmodels.ACCESS_FAILED)
        self.assertEquals(latest_audit.failures_since_start, 1)


    def testRepeatedFailedLogin(self):
        print "testRepeatedFailedLogin"
        from auditcare.decorators import login
        login.FAILURE_LIMIT = 3
        login.LOCK_OUT_AT_FAILURE=True
        login.COOLOFF_TIME = timedelta(seconds=4)

        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        response = self.client.post('/accounts/login/', {'username': 'mockmock@mockmock.com', 'password': 'wrongwrongwrong'})

        firstlogin_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEquals(start_count+1, firstlogin_count)


        first_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(first_audit.access_type, couchmodels.ACCESS_FAILED)
        self.assertEquals(first_audit.failures_since_start, 1)
        start_failures = first_audit.failures_since_start

        for n in range(1,3):
            #we are logging in within the cooloff period, so let's check to see if it doesn't increment.
            response = self.client.post('/accounts/login/', {'username': 'mockmock@mockmock.com', 'password': 'wrongwrongwrong'})
            next_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
            self.assertEquals(firstlogin_count, next_count)

            next_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
            self.assertEquals(next_audit.access_type, couchmodels.ACCESS_FAILED)
            self.assertEquals(next_audit.failures_since_start, n+start_failures)
            time.sleep(1)
        time.sleep(3)
        response = self.client.post('/accounts/login/', {'username': 'mockmock@mockmock.com', 'password': 'wrongwrong'})
        cooled_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEquals(cooled_audit.failures_since_start,1)



    def testAuditViews(self):
        for v in settings.AUDIT_VIEWS:
            pass
    