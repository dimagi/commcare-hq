from django.test.client import Client
from django.contrib.auth.models import User, AnonymousUser
from corehq.apps.auditor.models import AuditEvent, ModelActionAudit, AccessAudit
import unittest
import settings
from corehq.util.threadlocals import _thread_locals


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





class authenticationTestCase(unittest.TestCase):
    def setUp(self):
        if hasattr(_thread_locals, 'user'):
            delattr(_thread_locals, 'user')
        User.objects.all().delete()
        delete_all(AuditEvent, 'auditor/all_events')
        self.client = Client()
        self._createUser()
            
    def _createUser(self):
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
        self.assertEqual(start_count+1, logout_count)
        
        
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
    