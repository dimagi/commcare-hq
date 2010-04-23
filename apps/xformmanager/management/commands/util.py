""" Utility functions used by various xformmanager.management.commands """
from django.utils import simplejson
import urllib, httplib
from urlparse import urlparse

def submit_schema(filename, destination_url):
    """ registers a schema with a CommCareHQ server
    
    filename: name of schema file
    destination_url: server to submit to
    """
    fin = open(filename, "rb")
    # first line is the header dictionary
    dict_string = fin.readline()
    schema_dict = simplejson.loads(dict_string)
    # next line is empty
    fin.readline()
    # after that is everything else
    data = fin.read()
    fin.close()
    real_size = len(data)
    domain_name = schema_dict["domain"]
    schema_dict['content-length'] = real_size
    parsed_url = urlparse('http://%s/xforms/reregister/%s' % (destination_url, domain_name))
    schema_dict["is_resubmission" ] =  "True" 
    schema_dict["schema-type" ] =  "xsd" 
    schema_dict['User-Agent'] = 'CCHQ-submitfromfile-python-v0.1'
    try:
        #print "submitting from %s to: %s" % (filename, parsed_url.path)
        conn = httplib.HTTPConnection(parsed_url.netloc)
        conn.request('POST', parsed_url.path, data, schema_dict)
        resp = conn.getresponse()
        if resp.status != httplib.OK:
            print "problem submitting form: %s. Code is %s." % (filename, resp.status)
            # print "Response is: \n%s" % resp.read()  
        #results = resp.read()
    except Exception, e:
        print"problem submitting form: %s" % filename 
        print e
        return None
