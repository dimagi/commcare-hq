import sys
from datetime import datetime
import unittest
import os
import time


import subprocess
import sys
from subprocess import PIPE

serverhost = 'test.commcarehq.org'
#serverhost = 'localhost:8000'


curl_command = 'C:\curl\curl.exe'
#example post to a form
# -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/

class RegisterAndSubmit(unittest.TestCase):
    def setup(self):
        pass
    
    def _scanBlockForInt(self, results, startword,endtag):
        try:
            id_start = results.index(startword)            
            submit_len = len(startword)         
            
            sub_block = results[id_start:]               
            
            id_endtag = sub_block.index(endtag)
            submission_id = sub_block[submit_len:id_endtag]
            id = int(submission_id)
            return id
        except:
            return -1
        
    
#    def testCheckTestDirectoryIsCorrect(self):
#        curdir = os.path.dirname(__file__)
#        datadir = os.path.join(curdir,'data')
#        schemadir = os.path.join(curdir,'schemas')
#        
#        datafiles = os.listdir(datadir)
#        schemafiles = os.listdir(schemadir)        
#        
#        self.assertEquals(len(datafiles),len(schemafiles))        
#        
#        for i in range(0,len(datafiles)):
#            if datafiles[i] == ".svn":
#                continue
#            self.assertEquals(datafiles[i].split('.')[0],schemafiles[i].split('.')[0])
    
    def testPostAndVerifySchema(self):
        curdir = os.path.dirname(__file__)        
        schemadir = os.path.join(curdir,'schemas')        
        schemafiles = os.listdir(schemadir)
        
        for schemafile in schemafiles:
            time.sleep(.2)
            if schemafile == ".svn":
                continue            
            print schemafile
            fin = open(os.path.join(schemadir,schemafile),'r')
            schema = fin.read()
            fin.close()
            header_hash = {}
            header_hash['REMOTE_HOST']='127.0.0.1'
            header_hash['HTTP_X_FORWARDED_FOR']='127.0.0.1'            
            header_hash['CONTENT_LENGTH'] = len(schema)
            header_hash['HTTP_CONTENT_LENGTH'] = len(schema)
            header_hash['HTTP_CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
            header_hash['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
            header_hash["Accept"] = "text/plain"
            
            
            fullpath = os.path.join(schemadir,schemafile)
            
            p = subprocess.Popen([curl_command,'-c logincookie.txt', '-F username=brian', '-F password=test','--request', 'POST', 'http://%s/accounts/login/' % serverhost],stdout=PIPE,shell=False)
            results = p.stdout.read()
            
            print "posting %s" % fullpath            
            print ' '.join([curl_command,'-b logincookie.txt', '-F file=@%s' % fullpath, '-F form_display_name=%s' % schemafile[0:-4], '--request', 'POST', 'http://%s/xformmanager/register_xform/' % serverhost])
            p = subprocess.Popen([curl_command,'-b logincookie.txt', '-F file=@%s' % fullpath, '-F form_display_name=%s' % schemafile, '--request', 'POST', 'http://%s/xformmanager/register_xform/' % serverhost],stdout=PIPE,shell=False)
            results = p.stdout.read()
            
            #ok, verify that it's there.
            #self.assertEqual(1,results.count("<h2>Submission received, thank you</h2>",0,len(results)))
            
            #next, verify that there's an attachment there too            
                        
    def testPostAndVerifySimpleData(self):
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'data')        
        datafiles = os.listdir(datadir)
        for file in datafiles:
            time.sleep(.5)
            if file == ".svn":
                continue
            fullpath = os.path.join(datadir,file)
            fin = open(fullpath,'r')
            filestr= fin.read()
            fin.close()
            # -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/
            p = subprocess.Popen([curl_command,'--header','Content-type: text/xml', '--header', '"Content-length: %s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://%s/receiver/submit/' % serverhost],stdout=PIPE,shell=False)
            results = p.stdout.read()
#            self.assertEqual(1,results.count("<h2>Submission received, thank you</h2>",0,len(results)))
#            
#            submit_id = self._scanBlockForInt(results,"SubmitID:",'</p>')
#            self.assertNotEqual(-1,submit_id)        
#            
#            attachment_count = self._scanBlockForInt(results,"Attachments:",'</p>')
#            self.assertEqual(1,attachment_count)
            
    def testPostAndVerifyMultipart(self):
        
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'multipart')        
        datafiles = os.listdir(datadir)
        for file in datafiles:
            time.sleep(.2)
            if file == ".svn":
                continue
            fullpath = os.path.join(datadir,file)
            fin = open(fullpath,'rb')
            filestr= fin.read()
            fin.close()
            # -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/
            p = subprocess.Popen([curl_command,'--header','Content-type: multipart/mixed; boundary=newdivider', '--header', '"Content-length: %s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://%s/receiver/submit/' % serverhost],stdout=PIPE,shell=False)
            results = p.stdout.read()
        #    self.assertEqual(1,results.count("<h2>Submission received, thank you</h2>",0,len(results)))
            
#            submit_id = self._scanBlockForInt(results, "SubmitID:",'</p>')
#            self.assertNotEqual(-1,submit_id)        
#            
#            attachment_count = self._scanBlockForInt(results,"Attachments:",'</p>')
#            self.assertEqual(3,attachment_count)        
            
            
if __name__ == "__main__":
    unittest.main()

        
            
        