import sys
from datetime import datetime
import unittest
import os
import time
import uuid
import re
import subprocess
import sys
from subprocess import PIPE
import httplib
from urllib import urlencode
from urllib2 import urlopen, Request, HTTPRedirectHandler
import urllib2
import urllib
from cookielib import * 
from urlparse import urlparse

#serverhost = 'localhost'  #for you local developers on apache
#serverhost = 'localhost:8000' #for you local developers using runserver
serverhost = 'test.commcarehq.org' #for the actual server
curl_command = 'curl' #make sure curl is in your path


#example post to a form
# -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xforms/

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

def getFilesFromList(dirname, filename):
    fin = open(filename,'r')
    ret = []
    line = fin.readline()
    while line != '':
        ret.append(os.path.join(dirname,line))
    return ret


        
    
    

#def postSchema(self, submit_user, submit_pw, schema_prefix):
#schemafiles = getFiles('xforms','.xml', prefix=schema_prefix)


class DomainTestCase(unittest.TestCase):
    def setUp(self):
        self.username = ''
        self.password = ''
        self.prefix = ''
        self.domain_name = ''
        self.xform_hash = {}
        self.session_cookie=''        
        self.cookie_header = ''
        
        
        self._establishSession()
        
        
    def tearDown(self):
        os.remove(self.session_cookie)
        
    
    def _establishSession(self):
        self.session_cookie = os.path.join(os.path.dirname(__file__),str(uuid.uuid1()) + "_cookie.txt")
        p = subprocess.Popen([curl_command,'-c',self.session_cookie, '-F username=%s' % self.username, '-F password=%s' % self.password,'--request', 'POST', 'http://%s/accounts/login/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
        results = p.stdout.read()
        
    
    def _loadDataFilesList(self, xform_filepath):
                
        domain_dir = os.path.dirname(xform_filepath)     
        fname, ext = os.path.splitext(os.path.basename(xform_filepath))
        
        if os.path.exists(os.path.join(domain_dir, fname+'.lst')):
            fin = open(os.path.join(domain_dir, fname+'.lst'), 'r')
            files = fin.readlines()
            fin.close()
            return files
        else:
            return []
        
        
    def _loadFiles(self, dirname, extension):
        curdir = os.path.dirname(__file__)        
        domain_dir = os.path.join(curdir, self.prefix)        
        targetfiles = os.listdir(domain_dir)
        
        retfiles = []
        
        for f in targetfiles:
            if f == ".svn":                
                continue            
            if not f.endswith(extension):
                continue
            if self.prefix != None:
                if not f.startswith(self.prefix):
                    continue
            retfiles.append(os.path.join(domain_dir,f))
        return retfiles

        
    def _verifySchema(self, results, schema_name):        
        if results.count("Submit Error:") != 0:
            #self.fail( "Verify Schema, submission errors")
            print "Verify Schema, submission errors: \n%s" % results
            return -1
                        

        if results.count(schema_name) != 1:
            print "Verify Schema, schema did not save: \n%s" % results
            return -1
            #self.assertEqual(1, results.count(schema_name))
                    
        #get the schema id just created
        if results.count("Registration successful for xform id:") != 1:
            print "registration of xform id not successful: \n%s" % results
            return -1
        else:            
            idx = results.index("Registration successful for xform id:")
            substr = results[idx+37:]
            pidx = substr.index('</p>')
            
            schema_idstr= substr[0:pidx]
            
            try:
                schema_id=int(schema_idstr)
                return schema_id
            except:
                "Error, schema id could not be extracted: \n%s" % results
                return -1


    def _getMaxSchemaSubmitId(self, xform_id):
        url = 'http://%s/api/xforms/%d/?format=csv' % (serverhost, xform_id)
        p = subprocess.Popen([curl_command,'-b', self.session_cookie, url],stdout=PIPE,stderr=PIPE,shell=False)
        data = p.stdout.read()
        count = data.count('\n') - 1
        return count

    def _postXform2(self,submit_user, submit_pw, xformfile):
        # build opener with HTTPCookieProcessor
        
        o = self._doLogin(submit_user, submit_pw)
        # second request should automatically pass back any
        # cookies received during login... thanks to the HTTPCookieProcessor
        fin = open(xformfile,'r')
        schema = fin.read()
        fin.close()

        shortname = os.path.basename(xformfile)
        shortname = shortname.replace('.xml','')        
        shortname = shortname + "-" + str(uuid.uuid1())        
                
        param_dict = {'file': schema, 'form_display_name': shortname}
        p2 = urllib.urlencode(param_dict)        
        up = urlparse('http://%s/xforms/register/' % (serverhost))
        try:
            conn = httplib.HTTPConnection(up.netloc)
            conn.request('POST', up.path, p2, {'Content-Type': 'multipart/form-data', 'User-Agent': 'CCHQ-testRegisterAndSubmit-python-v0.1', 'Cookie':self.cookie_header})
            resp = conn.getresponse()
            
            data = resp.read()
        except:
            return None

        return self._verifySchema(data, shortname)


        
    def _postXform(self, submit_user, submit_pw, xformfile):
        """Does an authenticated CURL post of an xform.  Upon finishing the CURL, will do a GET off the server to see if the resultant xform is actually received correctly based upon a uuid displayname being picked""" 
        fin = open(xformfile,'r')
        schema = fin.read()
        fin.close()        
        
        shortname = os.path.basename(xformfile)
        shortname = shortname.replace('.xml','')
        
        shortname = shortname + "-" + str(uuid.uuid1())
        
        print "Posting Xform: %s" % shortname   
        #print ' '.join([curl_command,'-N', '-b',self.session_cookie, '-F file=@%s' % xformfile, '-F form_display_name=%s' % shortname, '--request', 'POST', 'http://%s/xforms/register/' % serverhost])
        p = subprocess.Popen([curl_command,'-b', self.session_cookie, '-F file=@%s' % xformfile, '-F form_display_name=%s' % shortname, '--request', 'POST', 'http://%s/xforms/register/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
        results = p.stdout.read()
        return self._verifySchema(results, shortname)
    
    def _verifySubmission(self, resultstring, num_attachments):
        """Verify that a raw xform submission is submitted and the correct reply comes back in.  This also checks to make sure that the attachments are parsed out correctly"""
        
        # this should == xformmanager.SUCCESSFUL_SUBMISSION
        rescount = resultstring.count("Thanks!")
        attachment_count = '[no attachment]'
        #self.assertEqual(1,rescount)
        if rescount != 1:
            msg = "Data submission failed, not successful: " + str(rescount)
            print msg
            print "===== xform =====pn%s" % resultstring
            self.fail(msg)
        else:
            attach_pattern = re.compile(r"<NumAttachments>(\d+)</NumAttachments>")
            try:
                matches = attach_pattern.search(resultstring)
                attachment_count = int(matches.groups()[0])
                self.assertEqual(attachment_count, num_attachments)
            except Exception, ex:
                msg = "Data submission error:  attachment not found: " + attachment_count + " Exception: " + str(ex)
                print "===== xform =====pn%s" % resultstring
                self.fail(msg)
        
    def _postSimpleData2(self, datafile,domain_name):
        """Pure python method to submit direct POSTs"""
        if datafile == ".svn" or datafile.endswith('.py'):
            return
        fin = open(os.path.join(os.path.dirname(__file__),datafile),'r')
        filestr= fin.read()
        fin.close()
        
        up = urlparse('http://%s/receiver/submit/%s' % (serverhost, domain_name))
        
        try:
            conn = httplib.HTTPConnection(up.netloc)
            conn.request('POST', up.path, filestr, {'Content-Type': 'text/xml', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
            resp = conn.getresponse()
            results = resp.read()            
        except (httplib.HTTPException, socket.error):            
            return None
        self._verifySubmission(results,1)
        return results
                    
    def _postSimpleData(self, datafile, domain_name):        
        """Curl method to do data POSTs"""
        if datafile == ".svn" or datafile.endswith('.py'):
            return
        fin = open(datafile,'r')
        filestr= fin.read()
        fin.close()
        print "Simple Submission: " + datafile
        command_arr = [curl_command, '--header','Content-type:text/xml', '--header', 'Content-length:%s' % len(filestr), '--data-binary', '@%s' % datafile, '--request', 'POST', 'http://%s/receiver/submit/%s' % (serverhost, self.domain_name)] # 
        print ' '.join(command_arr) 
        p = subprocess.Popen(command_arr,stdout=PIPE,stderr=PIPE,shell=False,close_fds=True)
        results, stderr = p.communicate()       
        
                
        if stderr.count("transfer closed") > 0:
            self.fail("Curl Error with connection premature closure")
        elif stderr.count("couldn't connect to host") > 0:
            self.fail("Curl error, connection timeout, host not reachable")
        self._verifySubmission(results,1)
        
        
    def _verifySchemaSubmits(self, form_id, formname):      
        
        print '\n\n****************\nverifySchemaSubmits for ' + formname
                
        
        datafiles = self._loadDataFilesList(formname)
        if len(datafiles) == 0:
            print "No instance data for " + formname
        
        last_id = self._getMaxSchemaSubmitId(form_id)
        new_id = -1
        for file in datafiles:            
            data_file = os.path.join(self.prefix,'data',file.strip())            
            submitresults = self._postSimpleData2(data_file, self.domain_name)  
            new_id = self._getMaxSchemaSubmitId(form_id)
            self.assertNotEqual(new_id, last_id)
            print "Submitted file: " + data_file + " Row ID: " + str(new_id)                     
            last_id = new_id
    
    def _doTest0PostXFormsAndVerify(self):
        """DomainTestCase doTest0PostXFormsAndVerify"""
        if self.username == '':
            print 'self.username is null'
            return
        
        xforms = self._loadFiles(self.prefix,'.xml')
        for xf in xforms:
            print xf
            form_id = self._postXform(self.username,self.password,xf)
            print "xform registration done for: " + xf + " id: " + str(form_id)
            if form_id > 0:                
                self.xform_hash[xf] = form_id
                self._verifySchemaSubmits(form_id, xf)
            else:
                msg = "xform registration failed for: " + xf
                
                self.fail(msg)


class TestDeployPathFinder(DomainTestCase):    
    def setUp(self):
        self.username = 'pfadmin'
        self.password = 'commcare123'
        self.prefix = 'pf'
        self.domain_name = 'pathfinder'
        self.xform_hash = {}
        self.cookie_header = ''
        self.session_cookie = ''
        self._establishSession()        
    
    def tearDown(self):
        try:
            os.remove(self.session_cookie)
        except:
            pass
    
    def test0PostXformsAndVerify(self):
        self._doTest0PostXFormsAndVerify()
            
   
    

class TestDeployPathBracCHW(DomainTestCase):    
    def setUp(self):
        self.username = 'brian'
        self.password = 'test'
        self.prefix = 'brac-chw'
        self.domain_name = 'BRAC'
        self.xform_hash = {}
        self.cookie_header = ''
        self.session_cookie = ''
        self._establishSession()        
    
    def tearDown(self):
        try:
            os.remove(self.session_cookie)
        except:
            pass
    
    def test0PostXformsAndVerify(self):
        self._doTest0PostXFormsAndVerify()
            
            
class TestDeployPathBracCHP(DomainTestCase):    
    def setUp(self):
        self.username = 'brian'
        self.password = 'test'
        self.prefix = 'brac-chp'
        self.domain_name = 'BRAC'
        self.xform_hash = {}
        self.cookie_header = ''
        self.session_cookie = ''
        self._establishSession()        
    
    def tearDown(self):
        try:
            os.remove(self.session_cookie)
        except:
            pass
    
    def test0PostXformsAndVerify(self):
        self._doTest0PostXFormsAndVerify()     
        

class TestDeployPathGrameen(DomainTestCase):    
    def setUp(self):
        self.username = 'gradmin'
        self.password = 'commcare123'
        self.prefix = 'mvp'
        self.domain_name = 'grameen'
        self.xform_hash = {}
        self.cookie_header = ''
        self.session_cookie = ''
        self._establishSession()        
    
    def tearDown(self):
        try:
            os.remove(self.session_cookie)
        except:
            pass
    
    def test0PostXformsAndVerify(self):
        self._doTest0PostXFormsAndVerify()     
        
    


class TestSimpleSubmits(unittest.TestCase):
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
        """Verify that a raw xform submission is submitted and the correct reply comes back in.  This also checks to make sure that the attachments are parsed out correctly"""
        rescount = resultstring.count("Submission received, thank you")
        attachment_count = '[no attachment]'
        #self.assertEqual(1,rescount)
        if rescount != 1:
            msg = "Data submission failed, not successful: " + str(rescount)
            print msg
            self.fail(msg)
            #print resultstring
        else:
            idx = resultstring.index("<p>Attachments:")
            attachment_count = resultstring[idx+15:].replace('</p>','')
            try:
                anum = int(attachment_count)
                self.assertEqual(anum, num_attachments)
                
            except:
                print "Data submission error:  attachment not found: " + attachment_count
                self.assertFalse(True)                        

    

    def testPostAndVerifyMultipart(self):       
        
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'multipart')        
        datafiles = os.listdir(datadir)
        for file in datafiles:
            if file == ".svn":
                continue
            fullpath = os.path.join(datadir,file)
            fin = open(fullpath,'rb')
            filestr= fin.read()
            fin.close()            
            # -F file=@schemas\2_types.xsd --request POST http://test.commcarehq.org/xforms/
            p = subprocess.Popen([curl_command,'--header','Content-type:multipart/mixed; boundary=newdivider', '--header', '"Content-length:%s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://%s/receiver/submit/Pathfinder/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()                
            #self._verifySubmission(results,3)
                        
            p = subprocess.Popen([curl_command,'--header','Content-type:multipart/mixed; boundary=newdivider', '--header', '"Content-length:%s' % len(filestr), '--data-binary', '@%s' % fullpath, '--request', 'POST', 'http://%s/receiver/submit/BRAC/' % serverhost],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()
            #self._verifySubmission(results,3)

class TestODKSubmit(unittest.TestCase):
    def setup(self):
        pass    
    
    def testPostLegacyXForm(self):               
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'odk')        
        fin = open(os.path.join(datadir,'xform.xml'),'r')
        filestr = fin.read()
        fin.close()
        
                
        p = subprocess.Popen([curl_command,
                              '--header',
                              'Content-type:text/xml', 
                              '--header', 
                              '"Content-length:%s' % len(filestr), 
                              '--data-binary', 
                              '@%s' % os.path.join(datadir,'xform.xml'), 
                              '--request', 
                              'POST', 
                              'http://%s/receiver/submit/BRAC/' % serverhost],
                              stdout=PIPE,stderr=PIPE,shell=False)
        
        
        print "executing testPostLegacyXForm"        
        results = p.stdout.read()            
        print results    
    
    
    
    def testPostSingleXForm(self):        
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'odk')
        xformpath = os.path.join(datadir,'xform.xml')        
        
        command_arr = [
                       curl_command, 
                      '-F xml_submission_file=@%s' % xformpath,                                                                                         
                      '--request', 'POST', 
                      'http://%s/receiver/submit/BRAC/' % serverhost
                      ]
    
        
        p = subprocess.Popen(command_arr,
                              stdout=PIPE,stderr=PIPE,shell=False)
        
        print "Executing testPostSingleXForm"
        print ' '.join(command_arr)
        p = subprocess.Popen(command_arr, stdout=PIPE,stderr=PIPE,shell=False)
        results = p.stdout.read()
        errors = p.stderr.read()        
        print results
        
    def testPostMultiPart(self):
        curdir = os.path.dirname(__file__)        
        datadir = os.path.join(curdir,'odk')
        xformpath = os.path.join(datadir,'xform.xml')        
        imagepath = os.path.join(datadir,'xform.xml')
        
        command_arr = [
                       curl_command, 
                      '-F xml_submission_file=@%s' % xformpath,                                                                                         
                      '-F file1.jpg=@%s' % imagepath,
                      '--request', 'POST', 
                      'http://%s/receiver/submit/BRAC/' % serverhost
                      ]
        print "Executing testPostMultipart"
        print ' '.join(command_arr)
        p = subprocess.Popen(command_arr, stdout=PIPE,stderr=PIPE,shell=False)
        results = p.stdout.read()
        errors = p.stderr.read()        
        print results
    

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
            p = subprocess.Popen([curl_command,'--header','Content-type: text/xml', '--header', 'Content-length: %s' % len(filestr), '--data-binary', '@%s' % file, '--request', 'POST', 'http://%s/receiver/backup/%s' % (serverhost,domain_name)],stdout=PIPE,stderr=PIPE,shell=False)
            results = p.stdout.read()
            #print "BackupRestore: " + results
            
            conn = httplib.HTTPConnection(serverhost)
            res = conn.request("GET", "/receiver/restore/%s" % (results))
            #print res
            r2 = conn.getresponse()
            #self.assertEquals(r2.status,200)
            
            restored = r2.read()
            
            if restored != filestr:
                msg = "BackupRestore error failed for id: " + results                
                print msg
                self.fail(msg)
            self.assertEquals(restored,filestr)

            
    def testPostFilesAsBackups(self):
        return
        # CZUE: was going to comment this out but i see it's already been hijacked
        # TODO: add/fix test with new backup and restore workflow.
        files = getFiles('brac-chw', '.xml')
        self._postSimpleData(files, 'BRAC')

        
            

if __name__ == "__main__":
    real_args = [sys.argv[0]]
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            argsplit = arg.split('=')
            if len(argsplit) == 2:
                if argsplit[0] == 'serverhost':
                    serverhost = argsplit[-1]                
                elif argsplit[0] == 'curlcommand':
                    curl_command = argsplit[-1]
                else:
                    raise "Error, these arguments are wrong, it should only be\nt\tserverhost=<hostname>\n\tcurlcommand=<curl command>\n\t\tand they BOTH must be there!"
            else:
                #it's not an argument we want to parse, so put it into the actual args
                real_args.append(arg)
        
    print curl_command
    
    unittest.main(argv=real_args)

        
            
        
