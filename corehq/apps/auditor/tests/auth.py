from django.test.client import Client
from django.contrib.auth.models import User, AnonymousUser
from corehq.apps.auditor.models import AuditEvent, ModelActionAudit, AccessAudit
import unittest
import settings

class authenticationTestCase(unittest.TestCase):
    def setUp(self):
        print "Starting up tests"
#        AuditEvent.objects.all().delete()
        self.client = Client()
        
        self._createUser()
            
    def _createUser(self):
        User.objects.all().delete()
        print "Creating Mock User"
        model_count = ModelActionAudit.objects.all().count()
        total_count = AuditEvent.objects.all().count()        
        
        usr = User()
        usr.username = 'mockmock'
        usr.set_password('mockmock')
        usr.first_name='mocky'
        usr.last_name = 'mock'
        usr.save()        

        model_count2 = ModelActionAudit.objects.all().count()
        total_count2 = AuditEvent.objects.all().count()
        
        self.assertEqual(model_count+1, model_count2)    
        self.assertEqual(total_count+1, total_count2)
    
    def testModifyUser(self):
        print "testModifyUser"
        model_count = ModelActionAudit.objects.all().count()
        total_count = AuditEvent.objects.all().count()        
        
        usr = User.objects.get(username='mockmock')
        usr.first_name='aklsjfl'
        usr.save()
        
        model_count2 = ModelActionAudit.objects.all().count()
        total_count2 = AuditEvent.objects.all().count()
                
        self.assertEqual(model_count+1, model_count2)    
        self.assertEqual(total_count+1, total_count2)
    
    
    def testLogin(self):
        print "testLogin"
        start_count = AccessAudit.objects.all().count()        
        response = self.client.post('/accounts/login/', {'username': 'mockmock', 'password': 'mockmock'})                
        login_count = AccessAudit.objects.all().count()     
        self.assertEqual(start_count+1, login_count)        
          
        response = self.client.post('/accounts/logout/', {})        
        logout_count = AccessAudit.objects.all().count()        
        self.assertEqual(start_count+2, logout_count)
        
        
    def testFailedLogin(self):
        print "testFailedLogin"
        start_count = AccessAudit.objects.all().count()        
        response = self.client.post('/accounts/login/', {'username': 'mockmock', 'password': 'asdfsdaf'})                
        access = AccessAudit.objects.order_by('-event_date')[0]
        
        self.assertEquals('failed', access.access_type)
        login_count = AccessAudit.objects.all().count()     
        self.assertEqual(start_count+1, login_count)
    
    def testAuditViews(self):
        for v in settings.AUDIT_VIEWS:
            pass
    