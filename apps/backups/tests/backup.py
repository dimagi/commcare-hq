import unittest
import os

from backups.models import Backup, BackupUser
from backups.processor import BACKUP_HANDLER, APP_NAME
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
        self.assertEqual(0, BackupUser.objects.count())
        self.assertEqual(0, Backup.objects.count())
        
        #submit the xml
        populate("backup.xml", path=data_path)
        
        # should create a user and a backup
        self.assertEqual(1, BackupUser.objects.count())
        self.assertEqual(1, Backup.objects.count())
        
        # and they should be mapped correctly with the data matching
        # the (hard-coded) data in the xml
        user = BackupUser.objects.all()[0]
        backup = Backup.objects.all()[0]
        self.assertEqual("siwema", user.username)
        self.assertEqual(1, backup.users.count())
        self.assertEqual(user, backup.users.all()[0])
        self.assertEqual("RKEBWRSWIAFQ5VGKRC93YBV2C", backup.device_id)
        
        # also, make sure we created an instance of the right handler
        way_handled = SubmissionHandlingOccurrence.objects.get\
                            (submission=backup.attachment.submission)
        self.assertEqual(APP_NAME, way_handled.handled.app)
        self.assertEqual(BACKUP_HANDLER, way_handled.handled.method)
        