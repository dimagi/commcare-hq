import unittest
from receiver.models import Submission, Attachment
from receiver.tests.util import *

class ProcessingTestCase(unittest.TestCase):

    def setUp(self):
        allsubmits = Submission.objects.all()
        for submit in allsubmits:
            submit.delete()

    def testSubmitSimple(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
        
        num = len(Submission.objects.all())
        makeNewEntry(get_full_path('simple-meta.txt'),
                     get_full_path('simple-body.txt'))
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
    
    def testDuplicates(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
        
        num = len(Submission.objects.all())
        self.assertEqual(0, num)
        # make a submission and ensure it's not considered a duplicate
        submission = makeNewEntry(get_full_path('simple-meta.txt'),
                                  get_full_path('simple-body.txt'))
        self.assertEqual(1,len(submission.attachments.all()))
        attachment = submission.attachments.all()[0]
        self.assertFalse(attachment.has_duplicate())
        self.assertFalse(attachment.is_duplicate())
        
        # duplicate it and make sure that both now have dupes, the
        # second one of which is a dupe
        dupe_submission = makeNewEntry(get_full_path('simple-meta.txt'),
                                       get_full_path('simple-body.txt'))
        self.assertEqual(1,len(dupe_submission.attachments.all()))
        dupe_attachment = dupe_submission.attachments.all()[0]
        self.assertTrue(dupe_attachment.has_duplicate())
        self.assertTrue(attachment.has_duplicate())
        self.assertTrue(dupe_attachment.is_duplicate())
        self.assertFalse(attachment.is_duplicate())
        
        
    
    def testCheckSimpleAttachments(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
                
        num = len(Submission.objects.all())
        makeNewEntry(get_full_path('simple-meta.txt'),
                     get_full_path('simple-body.txt'))
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
        mysub = Submission.objects.all()[0]
        
        attaches = Attachment.objects.all().filter(submission=mysub)        
        self.assertEquals(1,len(attaches))        
    
    def testCheckAttachmentSignals(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
        self.assertEqual(0, len(Submission.objects.all()))
        self.assertEqual(0, len(Attachment.objects.all()))
        
        makeNewEntry(get_full_path('simple-meta.txt'),
                     get_full_path('simple-body.txt'))
        
        self.assertEquals(1, len(Submission.objects.all()))
        mysub = Submission.objects.all()[0]
        
        self.assertEquals(1,len(mysub.attachments.all()))        
        
        # resaving the submission should NOT add a new attachment.
        mysub.content_type="something_else"
        mysub.save()
        self.assertEquals(1,len(mysub.attachments.all()))        
    
    
    def testSubmitMultipart(self):     
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
           
        num = len(Submission.objects.all())
        makeNewEntry(get_full_path('multipart-meta.txt'),
                     get_full_path('multipart-body.txt'))
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
    
    def testCheckMultipartAttachments(self):       
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
        
         
        num = len(Submission.objects.all())
        makeNewEntry(get_full_path('multipart-meta.txt'),
                     get_full_path('multipart-body.txt'))
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
        mysub = Submission.objects.all()[0]        
        attaches = Attachment.objects.all().filter(submission=mysub)     
        self.assertEquals(3,len(attaches))        
        
    def tearDown(self):
        pass

