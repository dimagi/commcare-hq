import sys
from datetime import datetime
import os
import time
import uuid
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
import re
import random


def post(serverhost, domain_name):
    create_xml()
    filename = r'testupload.xml'
    up = urlparse('http://%s/receiver/submit/%s' % (serverhost, domain_name))
    dict = {}
    dict['User-Agent'] = 'CCHQ-submitfromfile-python-v0.1'
    number = 0
    try:
        file = open(filename, "rb")
        data = file.read()
        dict["content-type"] = "text/xml"
        dict["content-length"] = len(data)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, data, dict)
        resp = conn.getresponse()
        results = resp.read()
        beg = re.search('<SubmissionId>', results).span()
        end = re.search('</SubmissionId>', results).span()
        number =  results[beg[1]:end[0]]
    except Exception, e:
        print"problem submitting form: %s" % filename 
        print e
    return number

def create_xml():
    f = open("testupload.xml", "w")
    xml_to_write = "<?xml version='1.0' ?><brac xmlns=\"http://dev.commcarehq.org/BRAC/CHP/coakley\">"
    i = 1
    while i < 4:
        random_num = random.randint(0, 100)
        xml_to_write = xml_to_write + "<Num%d>" % i
        xml_to_write = xml_to_write + str(random_num) 
        xml_to_write = xml_to_write + "</Num%d>" % i 
        i = i + 1
    xml_to_write = xml_to_write + "</brac>"
    f.write(xml_to_write)
    f.close()  

