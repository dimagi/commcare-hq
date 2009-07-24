import unittest
from receiver.models import *
from receiver import submitprocessor 
from organization.models import Domain

class ProcessingTestCase(unittest.TestCase):
    def setup(self):
        print "ProcessingTestCase.Setup()"
        
#        attaches = Attachment.objects.all()
#        for attach in attaches:
#            attach.delete()
#        
        allsubmits = Submission.objects.all()
        for submit in allsubmits:
            submit.delete()
        
        
#        submits = os.listdir(settings.XFORM_SUBMISSION_PATH)
#        self.assertEquals(0,len(submits))
#        
#        attaches = os.listdir(settings.ATTACHMENTS_PATH)
#        self.assertEquals(0,len(attaches))
    

    def testSubmitSimple(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
        
        num = len(Submission.objects.all())
        makeNewEntry('simple-meta.txt','simple-body.txt')
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
    
    def testDuplicates(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
        
        num = len(Submission.objects.all())
        self.assertEqual(0, num)
        # make a submission and ensure it's not considered a duplicate
        submission = makeNewEntry('simple-meta.txt','simple-body.txt')
        self.assertEqual(1,len(submission.attachments.all()))
        attachment = submission.attachments.all()[0]
        self.assertFalse(attachment.is_duplicate())
        
        # duplicate it and make sure that both are now considered dupes
        dupe_submission = makeNewEntry('simple-meta.txt','simple-body.txt')
        self.assertEqual(1,len(dupe_submission.attachments.all()))
        dupe_attachment = dupe_submission.attachments.all()[0]
        self.assertTrue(dupe_attachment.is_duplicate())
        self.assertTrue(attachment.is_duplicate())
        
        
    
    def testCheckSimpleAttachments(self):
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
                
        num = len(Submission.objects.all())
        makeNewEntry('simple-meta.txt','simple-body.txt')
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
        mysub = Submission.objects.all()[0]
        
        attaches = Attachment.objects.all().filter(submission=mysub)        
        self.assertEquals(1,len(attaches))        
    
    
    def testSubmitMultipart(self):     
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
           
        num = len(Submission.objects.all())
        makeNewEntry('multipart-meta.txt','multipart-body.txt')
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
    
    def testCheckMultipartAttachments(self):       
        Submission.objects.all().delete()
        Attachment.objects.all().delete()
        
         
        print '############################### testCheckMultipartAttachments'
        num = len(Submission.objects.all())
        makeNewEntry('multipart-meta.txt','multipart-body.txt')
        num2 = len(Submission.objects.all())        
        self.assertEquals(num+1,num2)
        mysub = Submission.objects.all()[0]        
        attaches = Attachment.objects.all().filter(submission=mysub)     
        self.assertEquals(3,len(attaches))        
        
    def tearDown(self):
        print "ProcessingTestCase.tearDown()"


def makeNewEntry(headerfile, bodyfile):
    fin = open(os.path.join(os.path.dirname(__file__),headerfile),"r")
    meta= fin.read()
    fin.close()
    
    fin = open(os.path.join(os.path.dirname(__file__),bodyfile),"rb")
    body = fin.read()
    fin.close()
    
    metahash = eval(meta)
    if Domain.objects.all().count() == 0:
        mockdomain = Domain(name='mockdomain')
        mockdomain.save()
    else:
        mockdomain = Domain.objects.all()[0]
    return submitprocessor.do_raw_submission(metahash, body, domain=mockdomain)
