from django.test import TestCase
import os
import time
from couchforms.util import post_xform_to_couch
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.signals import process_cases
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.phone.tests import const
from casexml.apps.phone.tests.dummy import dummy_user
from couchforms.models import XFormInstance

class SyncTokenUpdateTest(TestCase):
    """
    Tests sync token updates on submission
    """
        
    def setUp(self):
        # clear cases
        for item in XFormInstance.view("couchforms/by_xmlns", include_docs=True, reduce=False).all():
            item.delete()
        for case in CommCareCase.view("case/by_xform_id", include_docs=True).all():
            case.delete()
        for log in SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all():
            log.delete()
    
    def _postWithSyncToken(self, filename, token_id):
        file_path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        
        # set last sync token on the form before saving
        form.last_sync_token = token_id
        process_cases(sender="testharness", xform=form)
        
        
    def _checkLists(self, l1, l2):
        self.assertEqual(len(l1), len(l2))
        for i in l1:
            self.assertTrue(i in l2, "%s found in %s" % (i, l2))
        for i in l2:
            self.assertTrue(i in l1, "%s found in %s" % (i, l1))
    
    def _testUpdate(self, sync_id, create_list, update_list, close_list, form_list):
        log = SyncLog.get(sync_id)
        self._checkLists(log.created_cases, create_list)
        self._checkLists(log.updated_cases, update_list)
        self._checkLists(log.closed_cases, close_list)
        self._checkLists(log.submitted_forms, form_list)
        
    def testInitialEmpty(self):
        """
        Tests that a newly created sync token has no cases attached to it.
        """
        restore_payload = generate_restore_payload(dummy_user())
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        self._testUpdate(sync_log.get_id, [], [], [], [])
        
    def testTokenAssociation(self):
        """
        Test that individual create, update, and close submissions update
        the appropriate case lists in the sync token
        """
        restore_payload = generate_restore_payload(dummy_user())
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        cases = ["asdf"]
        forms = ["someuid"]
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, cases, [], [], forms)
        
        forms.append("somenewuid")
        self._postWithSyncToken("update_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, cases, cases, [], forms)
        
        forms.append("someothernewuid")
        self._postWithSyncToken("close_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, cases, cases, cases, forms)
    
    def testMultipleUpdates(self):
        """
        Test that multiple update submissions update the case lists 
        and don't create duplicates in them
        """
        
        restore_payload = generate_restore_payload(dummy_user())
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        cases = ["asdf"]
        forms = ["someuid", "somenewuid"]
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        self._postWithSyncToken("update_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, cases, cases, [], forms)
        
        forms.append("somenewuid2")
        self._postWithSyncToken("update_short_2.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, cases, cases, [], forms)
        
    def testMultiplePartsSingleSubmit(self):
        restore_payload = generate_restore_payload(dummy_user())
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        cases = ["IKA9G79J4HDSPJLG3ER2OHQUY"]
        forms = ["33UP8MOWL8CQNERTDYAHRPVJG"]
        self._postWithSyncToken("case_create.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, cases, cases, [], forms)

    def testMultipleForms(self):
        restore_payload = generate_restore_payload(dummy_user())
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        cases = ["asdf"]
        forms = ["someuid"]
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, cases, [], [], forms)
        
        new_cases = ["IKA9G79J4HDSPJLG3ER2OHQUY"]
        both_cases = ["asdf", "IKA9G79J4HDSPJLG3ER2OHQUY"]
        
        forms.append("33UP8MOWL8CQNERTDYAHRPVJG")
        self._postWithSyncToken("case_create.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, both_cases, new_cases, [], forms)

