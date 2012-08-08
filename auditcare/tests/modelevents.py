import pdb
import unittest
import time
from auditcare.inspect import history_for_doc
from auditcare.utils import _thread_locals
from django.contrib.auth.models import User
from auditcare.models import AuditEvent, ModelActionAudit
from auditcare.tests.testutils import delete_all
from django_digest.test import Client

class modelEventTestCaseo(unittest.TestCase):
    def setUp(self):
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
        usr.email = 'nothing@nothing.com'
        usr.save()

        self.user = usr

        model_count2 = ModelActionAudit.view("auditcare/model_actions_by_id", include_docs=True, reduce=False).count()
        total_count2 = AuditEvent.view("auditcare/all_events").count()

        self.assertEqual(model_count+1, model_count2)
        self.assertEqual(total_count+1, total_count2)
        return usr


    def testModelEventChanges(self):
        """
        Test that django model events do change.  A single change
        """
        model_count = ModelActionAudit.view("auditcare/model_actions_by_id", include_docs=True, reduce=False).count()

        self.user.email='foo@foo.com'
        time.sleep(1)
        self.user.save()
        time.sleep(1)

        model_count2 = ModelActionAudit.view("auditcare/model_actions_by_id", include_docs=True, reduce=False).count()
        self.assertEqual(model_count+1, model_count2)


        #Filter for email and see if it shows up
        email_wrapper = history_for_doc(self.user, filter_fields=['email'])
        email_narratives = email_wrapper.change_narratives()
        self.assertEqual(1, len(email_narratives))

        #exclude for email and see if it doesn't show up
        exclude_wrapper = history_for_doc(self.user, exclude_fields=['email'])
        exclude_narratives = exclude_wrapper.change_narratives()
        self.assertEqual(0, len(exclude_narratives))

        #exclude and filter for email and see if it doesn't show up
        exclude_wrapper = history_for_doc(self.user, filter_fields=['email'], exclude_fields=['email'])
        exclude_narratives = exclude_wrapper.change_narratives()
        self.assertEqual(0, len(exclude_narratives))


        #Filter for email and see if it shows up
        new_last_name = 'alksjflajdsflkjsadf'
        self.user.last_name= new_last_name
        time.sleep(1)
        self.user.save()

        name_change_wrapper = history_for_doc(self.user, filter_fields=['email', 'first_name', 'last_name'])
        name_change_narratives = name_change_wrapper.change_narratives()

        change_generator = name_change_narratives[-1]['changes']

        seen_last_name = False
        seen_old_value = False
        seen_new_value = False
        for ctuple in change_generator:
            if ctuple[0] == 'last_name':
                seen_last_name = True
            if ctuple[1][0] == 'mock':
                seen_old_value = True
            if ctuple[1][1] == new_last_name:
                seen_new_value = True
        self.assertTrue(seen_last_name)
        self.assertTrue(seen_old_value)
        self.assertTrue(seen_new_value)



