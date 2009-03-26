import unittest
from submitlogger.models import *
from submitlogger import submitprocessor 

class ProcessingTestCase(unittest.TestCase):
    def setup(self):
        print "ProcessingTestCase.Setup()"
        
#        attaches = Attachment.objects.all()
#        for attach in attaches:
#            attach.delete()
#        
        allsubmits = SubmitLog.objects.all()
        for submit in allsubmits:
            submit.delete()
        
        
#        submits = os.listdir(settings.XFORM_SUBMISSION_PATH)
#        self.assertEquals(0,len(submits))
#        
#        attaches = os.listdir(settings.ATTACHMENTS_PATH)
#        self.assertEquals(0,len(attaches))
    
    def _makeNewEntry(self,headerfile, bodyfile):
        newsubmit = SubmitLog()
        fin = open(os.path.join(os.path.dirname(__file__),headerfile),"r")
        meta= fin.read()
        fin.close()
        
        fin = open(os.path.join(os.path.dirname(__file__),bodyfile),"rb")
        body = fin.read()
        fin.close()
        
        metahash = eval(meta)
        submitprocessor.do_raw_submission(metahash, body)

    def testSubmitSimple(self):        
        SubmitLog.objects.all().delete()
        Attachment.objects.all().delete()
        
        num = len(SubmitLog.objects.all())
        self._makeNewEntry('simple-meta.txt','simple-body.txt')
        num2 = len(SubmitLog.objects.all())        
        self.assertEquals(num+1,num2)
    
    def testCheckSimpleAttachments(self):
        SubmitLog.objects.all().delete()
        Attachment.objects.all().delete()
                
        num = len(SubmitLog.objects.all())
        self._makeNewEntry('simple-meta.txt','simple-body.txt')
        num2 = len(SubmitLog.objects.all())        
        self.assertEquals(num+1,num2)
        mysub = SubmitLog.objects.all()[0]
        
        attaches = Attachment.objects.all().filter(submission=mysub)        
        self.assertEquals(1,len(attaches))        
    
    
    def testSubmitMultipart(self):     
        SubmitLog.objects.all().delete()
        Attachment.objects.all().delete()
           
        num = len(SubmitLog.objects.all())
        self._makeNewEntry('multipart-meta.txt','multipart-body.txt')
        num2 = len(SubmitLog.objects.all())        
        self.assertEquals(num+1,num2)
    
    def testCheckMultipartAttachments(self):       
        SubmitLog.objects.all().delete()
        Attachment.objects.all().delete()
         
        print '############################### testCheckMultipartAttachments'
        num = len(SubmitLog.objects.all())
        self._makeNewEntry('multipart-meta.txt','multipart-body.txt')
        num2 = len(SubmitLog.objects.all())        
        self.assertEquals(num+1,num2)
        mysub = SubmitLog.objects.all()[0]        
        attaches = Attachment.objects.all().filter(submission=mysub)     
        self.assertEquals(3,len(attaches))        
        
    def tearDown(self):
        print "ProcessingTestCase.tearDown()"
#        attaches = Attachment.objects.all()
#        for attach in attaches:
#            attach.delete()
        
#        allsubmits = SubmitLog.objects.all()
#        for submit in allsubmits:
#            submit.delete()
#        
        
#        submits = os.listdir(settings.XFORM_SUBMISSION_PATH)
#        self.assertEquals(0,len(submits))        
#        attaches = os.listdir(settings.ATTACHMENTS_PATH)
#        self.assertEquals(0,len(attaches))
        
       
