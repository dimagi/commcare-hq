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

#serverhost = 'dev.commcarehq.org'
#serverhost = 'localhost'
serverhost = 'localhost:8000'

curl_command = 'c:\curl\curl.exe'
#curl_command = 'curl'



filename = r'C:\Source\hq\data\debug\1727.xml'
domain_name = "Pathfinder"
up = urlparse('http://%s/receiver/submit/%s' % (serverhost, domain_name))
dict = {}
dict['User-Agent'] = 'CCHQ-submitfromfile-python-v0.1'
try:
    file = open(filename, "rb")
    data = file.read()
    dict["content-type"] = "text/xml"
    dict["content-length"] = len(data)
    conn = httplib.HTTPConnection(up.netloc)
    conn.request('POST', up.path, data, dict)
    resp = conn.getresponse()
    results = resp.read()
    print "Got back\n%s" % results
except Exception, e:
    print"problem submitting form: %s" % filename 
    print e
    
