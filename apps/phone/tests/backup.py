import unittest
import os

from phone.models import PhoneBackup
from phone.processor import BACKUP_HANDLER, APP_NAME
from receiver.models import SubmissionHandlingOccurrence
from xformmanager.tests.util import populate

class BackupTestCase(unittest.TestCase):
    
    def setUp(self):
        pass
    
    def tearDown(self):
        pass
    
    def testBasic(self):
        """Test basic backup functionality - create a backup by faking
           a post and make sure everything was created properly"""
        
        path = os.path.dirname(__file__)
        data_path = os.path.join(path, "data")
        
        # Make sure there's nothing to start
        self.assertEqual(0, PhoneBackup.objects.count())
        
        #submit the xml
        populate("backup.xml", path=data_path)
        
        # should create a backup
        self.assertEqual(1, PhoneBackup.objects.count())
        
        # and they should be mapped correctly with the data matching
        # the (hard-coded) data in the xml
        backup = PhoneBackup.objects.all()[0]
        self.assertEqual("RKEBWRSWIAFQ5VGKRC93YBV2C", backup.phone.device_id)
        
        # also, make sure we created an instance of the right handler
        way_handled = SubmissionHandlingOccurrence.objects.get\
                            (submission=backup.attachment.submission)
        self.assertEqual(APP_NAME, way_handled.handled.app)
        self.assertEqual(BACKUP_HANDLER, way_handled.handled.method)
        