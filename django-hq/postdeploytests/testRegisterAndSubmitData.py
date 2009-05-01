import sys
from datetime import datetime
import unittest
import os
import time
import uuid

import subprocess
import sys
from subprocess import PIPE
import httplib


serverhost = 'test.commcarehq.org'
curl_command = 'c:\curl\curl.exe'

#serverhost = 'localhost:8000'
#curl_command = 'curl'

#example post to a form
# -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/

def getFiles(dirname, extension, prefix=None):
    curdir = os.path.dirname(__file__)        
    targetdir = os.path.join(curdir, dirname)        
    targetfiles = os.listdir(targetdir)
    
    retfiles = []
    
    for f in targetfiles:
        if f == ".svn":                
            continue            
        if not f.endswith(extension):
            continue
        if prefix != None:
            if not f.startswith(prefix):
                continue
        retfiles.append(os.path.join(targetdir,f))
    return retfiles


class TestRegisterXforms(unittest.TestCase):
    def setup(self):
        pass
    
    
    def _verifySchema(self, results, schema_name):        
        self.assertEquals(0, results.count("Submit Error:"))
        self.assertEqual(1, results.count(schema_name))
            

    def _postSchemas(self, submit_user, submit_pw, schema_prefix):
        schemafiles = getFiles('xforms','.xml', prefix=schema_prefix)        
        for schemafile in schemafiles:            
            time.sleep(.1)            
            fin = open(schemafile,'r')
            schema = fin.read()
            fin.close()
            
            p = subprocess.Popen([curl_command,'-c logincookie.txt', '-F username=%s' % submit_user, '-F password=%s' % submit_pw,'--request', 'POST', 'http://%s/accounts/login/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()
            shortname = os.path.basename(schemafile)
            shortname = shortname.replace('.xml','')
            
            shortname = shortname + "-" + str(uuid.uuid1())
            
            print "Posting Xform: %s" % shortname   
            print ' '.join([curl_command,'-b logincookie.txt', '-F file=@%s' % schemafile, '-F form_display_name=%s' % shortname, '--request', 'POST', 'http://%s/xformmanager/register_xform/' % serverhost])
            p = subprocess.Popen([curl_command,'-b logincookie.txt', '-F file=@%s' % schemafile, '-F form_display_name=%s' % shortname, '--request', 'POST', 'http://%s/xformmanager/register_xform/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()
            self._verifySchema(results, shortname)
            
    def testPostAndVerifyBracSchemas(self):        
        self._postSchemas('brian','test','brac-')                
        
    def testPostAndVerifyPFSchemas(self):        
        self._postSchemas('pfadmin','commcare123','pf-')
        
    def testPostAndVerifyGrameenSchemas(self):        
        self._postSchemas('gradmin','commcare123','grameen_')


class TestSubmitData(unittest.TestCase):
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
        
    def _verifySubmission(self, resultstring, num_attachments):
        rescount = resultstring.count("Submission received, thank you")
        self.assertEqual(1,rescount)
        idx = resultstring.index("<p>Attachments:")
        attachment_count = resultstring[idx+8:].replace('</p>','')
        try:
            anum = int(attachment_count)
            self.assertEqual(anum, num_attachments)
        except:
            self.assertFalse(True)
        
        
        
        
                        
    def _postSimpleData(self, datafiles, domain_name):    
        
        for file in datafiles:
            #time.sleep(.1)
            if file == ".svn":
                continue
            fin = open(file,'r')
            filestr= fin.read()
            fin.close()
            print "Simple Submission: " + file
            command_arr = [curl_command,'--header','Content-type: text/xml', '--header', 'Content-length: %s' % len(filestr), '--data-binary', '@%s' % file, '--request', 'POST', 'http://%s/receiver/submit/%s' % (serverhost, domain_name)]
            print ' '.join(command_arr) 
            p = subprocess.Popen(command_arr,stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()
            self._verifySubmission(results,1)

    def testPostAndVerifyMultipart(self):        
        return
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'multipart')        
        datafiles = os.listdir(datadir)
        for file in datafiles:
#            time.sleep(.1)
            if file == ".svn":
                continue
            fullpath = os.path.join(datadir,file)
            fin = open(fullpath,'rb')
            filestr= fin.read()
            fin.close()
            # -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/
            p = subprocess.Popen([curl_command,'--header','Content-type: multipart/mixed; boundary=newdivider', '--header', '"Content-length: %s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://%s/receiver/submit/Pathfinder/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()                
            self._verifySubmission(results,3)
            
            
            p = subprocess.Popen([curl_command,'--header','Content-type: multipart/mixed; boundary=newdivider', '--header', '"Content-length: %s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://%s/receiver/submit/BRAC/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()
            self._verifySubmission(results,3)
            
    def testPostBracCHW(self):        
        files = getFiles('brac-chw', '.xml')
        self._postSimpleData(files, 'BRAC')
    
    def testPostBracCHP(self):
        
        files = getFiles('brac-chp', '.xml')
        self._postSimpleData(files, 'BRAC')
        
    def testPostPF(self):
        files = getFiles('pf', '.xml')
        self._postSimpleData(files, 'Pathfinder')       
    
    def testPostOther(self):
        
        files = getFiles('data', '.xml')
        self._postSimpleData(files, 'grameen')


class TestBackupRestore(unittest.TestCase):
    def setup(self):
        pass    
    def _postSimpleData(self, datafiles, domain_name):    
        
        for file in datafiles:
            #time.sleep(.1)
            if file == ".svn":
                continue
            fin = open(file,'r')
            filestr= fin.read()
            fin.close()
            print "Backup/Restore Test: " + file
            p = subprocess.Popen([curl_command,'--header','Content-type: text/xml', '--header', 'Content-length: %s' % len(filestr), '--data-binary', '@%s' % file, '--request', 'POST', 'http://%s/receiver/backup/%s/' % (serverhost,domain_name)],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()
            #print "BackupRestore: " + results
            
            conn = httplib.HTTPConnection(serverhost)
            res = conn.request("GET", "/receiver/restore/%s" % (results))
            #print res
            r2 = conn.getresponse()
            #self.assertEquals(r2.status,200)
            
            restored = r2.read()
            self.assertEquals(restored,filestr)



            
    def testPostFilesAsBackups(self):
        files = getFiles('brac-chw', '.xml')
        self._postSimpleData(files, 'BRAC')

        
            
if __name__ == "__main__":
    unittest.main()

        
            
        
