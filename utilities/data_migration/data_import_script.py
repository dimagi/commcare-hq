import sys
from datetime import datetime
import os
import time
import uuid
import json
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

#serverhost = 'test.commcarehq.org'
#serverhost = 'localhost'
serverhost = 'localhost:8000'
#serverhost = 'dev.commcarehq.org'

curl_command = 'c:\curl\curl.exe'
#curl_command = 'curl'

directory = r'C:\Source\hq\data\single_grameen'

def run(argv):

    if len(argv) > 1:
        directory = argv[1]
    # loop through once uploading all the schemas
    files = os.listdir(directory)
    for file in files:
        if "xsdexport" in file:
            _submit_schema(os.path.join(directory,file))
    
    # then a second time with all the instances
    total = len(files)
    count =0
    for file in files:
        if "postexport" in file:
            _submit_form(os.path.join(directory,file))
            if count % 100 == 0:
                print "uploaded %s of %s xforms" % (count, total)
                sys.stderr.write("uploaded %s of %s xforms\n" % (count, total))
                time.sleep(5)
            count = count + 1
    print "done"
    
def _submit_schema(filename):
    file = open(filename, "rb")
    # first line is the header dictionary
    dict_string = file.readline()
    dict = json.loads(dict_string)
    # next line is empty
    file.readline()
    # after that is everything else
    data = file.read()
    file.close()
    real_size = len(data)
    domain_name = dict["domain"]
    dict['content-length'] = real_size
    up = urlparse('http://%s/xforms/reregister/%s' % (serverhost, domain_name))
    dict["is_resubmission" ] =  "True" 
    dict["schema-type" ] =  "xsd" 
    dict['User-Agent'] = 'CCHQ-submitfromfile-python-v0.1'
    try:
        #print "submitting from %s to: %s" % (filename, up.path)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, data, dict)
        resp = conn.getresponse()
        results = resp.read()
    except Exception, e:
        print"problem submitting form: %s" % filename 
        print e
        return None
    

def _submit_form(filename):
    file = open(filename, "rb")
    # first line is the header dictionary
    dict_string = file.readline()
    dict = json.loads(dict_string)
    # next line is empty
    file.readline()
    # after that is everything else
    data = file.read()
    file.close()
    real_size = len(data)
    content_length = dict['content-length']
    domain_name = dict["domain"]
    # czue - temporarily don't sumbit pf and brac data since it comes
    # from supervisor
    
#    if domain_name == "Pathfinder" or domain_name == "BRAC":
#        print "skipping domain: %s" % domain_name
#        return 
#        
    if int(real_size) != int(content_length):
        print "form %s has mismatched size and content-length %s != %s, automatically fixing!" % (filename, real_size, content_length)
        dict['content-length'] = real_size
    up = urlparse('http://%s/receiver/resubmit/%s' % (serverhost, domain_name))
    dict["is_resubmission" ] =  "True" 
    dict['User-Agent'] = 'CCHQ-submitfromfile-python-v0.1'
    try:
        #print "submitting from %s to: %s" % (filename, up.path)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, data, dict)
        resp = conn.getresponse()
        results = resp.read()
        if not "thank you" in results:
            print "unexpected response for %s\n%s" % (filename, results)
        else:
            print "%s: success!" % filename
    except Exception, e:
        print"problem submitting form: %s" % filename 
        print e
        return None
    
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
    run(argv=real_args)

