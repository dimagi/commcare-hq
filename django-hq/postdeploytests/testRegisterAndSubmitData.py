import sys
from datetime import datetime
import unittest
import os


import subprocess
import sys
from subprocess import PIPE


sys.path.append(os.path.join(os.path.dirname(__file__),"../scripts"))
import formposter

curl_command = 'C:\curl\curl.exe'
#example post to a form
# -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/

class RegisterAndSubmit(unittest.TestCase):
    def setup(self):
        pass
    
    
    def testCheckTestDirectoryIsCorrect(self):
        curdir = os.path.dirname(__file__)
        datadir = os.path.join(curdir,'data')
        schemadir = os.path.join(curdir,'schemas')
        
        datafiles = os.listdir(datadir)
        schemafiles = os.listdir(schemadir)        
        
        self.assertEquals(len(datafiles),len(schemafiles))        
        
        for i in range(0,len(datafiles)):
            if datafiles[i] == ".svn":
                continue
            self.assertEquals(datafiles[i].split('.')[0],schemafiles[i].split('.')[0])
    
    def testPostAndVerifySchema(self):
        return
        curdir = os.path.dirname(__file__)        
        schemadir = os.path.join(curdir,'schemas')        
        schemafiles = os.listdir(schemadir)
        
        for schemafile in schemafiles:
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
            print "posting %s" % fullpath
            #results = formposter.do_httplib_post('test.commcarehq.org','/xformmanager/', header_hash, params)            
            #results = formposter.do_urllib2_post('http://localhost:8000','/xformmanager/',header_hash,params)
            #results = formposter.do_urllib_post('http://localhost:8000','/xformmanager/',params)
            #-F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/
            p = subprocess.Popen([curl_command,'-F file=@%s' % fullpath, '--request', 'POST', 'http://localhost:8000/xformmanager/'],stdout=PIPE,shell=False)
            results = p.stdout.read()
            print results
            
            
            
    def testPostAndVerifySimpleData(self):
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'data')        
        datafiles = os.listdir(datadir)
        for file in datafiles:
            fullpath = os.path.join(datadir,file)
            fin = open(fullpath,'r')
            filestr= fin.read()
            fin.close()
            # -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/
            p = subprocess.Popen([curl_command,'--header','Content-type: text/xml', '--header', '"Content-length: %s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://localhost:8000/formreceiver/submit/'],stdout=PIPE,shell=False)
            results = p.stdout.read()
            self.assertEqual(1,results.count("<h2>Submission received, thank you</h2>",0,len(results)))        
            
    def testPostAndVerifyMultipart(self):
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'multipart')        
        datafiles = os.listdir(datadir)
        for file in datafiles:
            fullpath = os.path.join(datadir,file)
            fin = open(fullpath,'rb')
            filestr= fin.read()
            fin.close()
            # -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xformmanager/
            p = subprocess.Popen([curl_command,'--header','Content-type: multipart/mixed; boundary=newdivider', '--header', '"Content-length: %s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://localhost:8000/formreceiver/submit/'],stdout=PIPE,shell=False)
            results = p.stdout.read()
            self.assertEqual(1,results.count("<h2>Submission received, thank you</h2>",0,len(results)))        
            
            
if __name__ == "__main__":
    unittest.main()

        
            
        