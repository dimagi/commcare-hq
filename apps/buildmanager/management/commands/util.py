""" Utility functions used by various xformmanager.management.commands """
import logging
from django.utils import simplejson
from urlparse import urlparse
import urllib, urllib2, httplib

def submit_form(filename, destination_url):
    """ Submits a submission to a CommCareHQ server
    
    filename: name of submission file
    destination_url: server to submit to
    """
    fin = open(filename, "rb")
    # first line is the header dictionary
    dict_string = fin.readline()
    submit_dict = simplejson.loads(dict_string)
    # next line is empty
    fin.readline()
    # after that is everything else
    data = fin.read()
    fin.close()
    real_size = len(data)
    content_length = submit_dict['content-length']
    domain_name = submit_dict["domain"]
    if int(real_size) != int(content_length):
        print "form %s has mismatched size and content-length %s != %s, automatically fixing!" % (filename, real_size, content_length)
        submit_dict['content-length'] = real_size
    parsed_url = urlparse('http://%s/receiver/resubmit/%s' % (destination_url, domain_name))
    submit_dict["is_resubmission" ] =  "True" 
    submit_dict['User-Agent'] = 'CCHQ-submitfromfile-python-v0.1'
    try:
        #print "submitting from %s to: %s" % (filename, parsed_url.path)
        conn = httplib.HTTPConnection(parsed_url.netloc)
        conn.request('POST', parsed_url.path, data, submit_dict)
        resp = conn.getresponse()
        results = resp.read()
        if not "thank" in results.lower():
            print "unexpected response for %s\n%s" % (filename, results)
    except Exception, e:
        print"problem submitting form: %s" % filename 
        print e
        return None
