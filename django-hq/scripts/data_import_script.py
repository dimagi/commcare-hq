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

curl_command = 'c:\curl\curl.exe'
#curl_command = 'curl'


def run(argv):
    directory = r'C:\Source\hq\commcare-hq\django-hq\bad'
    #directory = r'C:\Source\hq\commcare-hq\django-hq\export'
    if len(argv) > 1:
        directory = argv[1]
    for file in os.listdir(directory):
        if "postexport" in file:
            _submit(os.path.join(directory,file))
    print "done"
    
def _submit(filename):
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
        #print results
    except Exception, e:
        print"problem submitting form: %s" % filename 
        print e
        return None
    
def _postData(filename,domain_name):
    """Pure python method to submit direct POSTs"""
    if filename == ".svn" or filename.endswith('.py'):
        return
    fin = open(filename,'r')
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

        
            
        
