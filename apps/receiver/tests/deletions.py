import unittest
from receiver.models import Submission, Attachment, SubmissionHandlingOccurrence
from receiver.tests.util import *

class DeletionTestCase(unittest.TestCase):

    def setUp(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()

    def testDeleteSubmission(self):
        submission = makeNewEntry(get_full_path('multipart-meta.txt'),
                     get_full_path('multipart-body.txt'))
        count = len(Submission.objects.all())
        self.assertEquals(1,count)
        count = len(Attachment.objects.all())
        self.assertEquals(3,count)
        submission.delete()
        count = len(Submission.objects.all())
        self.assertEquals(0,count)
        count = len(Attachment.objects.all())
        self.assertEquals(0,count)
    
    def tearDown(self):
        pass

