from __future__ import absolute_import
import os
from urlparse import urlparse
import httplib
import subprocess
import tempfile
from subprocess import PIPE
from restkit import Resource, BasicAuth

def post_authenticated_data(data, url, username, password):
    """
    Post basic authenticated data, using restkit
    """ 
    auth = BasicAuth(username, password)
    r = Resource(url, filters=[auth, ])
    return (r.post(payload=data).body_string(), None)
    
def post_authenticated_file(filename, url, username, password):
    """
    Post basic authenticated file, using restkit
    """ 
    file = open(filename, "rb")
    try:
        return post_authenticated_data(file.read(), url, username, password)
    finally:
        file.close()
    
def post_data(data, url,curl_command="curl", use_curl=False,
    content_type = "text/xml"):
    """
    Do a POST of data with some options.  Returns a tuple of the response
    from the server and any errors
    """
    tmp_file_handle, tmp_file_path = tempfile.mkstemp()
    tmp_file = open(tmp_file_path, "w")
    try:
        tmp_file.write(data)
    finally:
        tmp_file.close()
        os.close(tmp_file_handle)

    return post_file(tmp_file_path, url, curl_command, use_curl, content_type)
    
def post_file(filename, url, curl_command="curl", use_curl=False,
              content_type = "text/xml", use_chunked=False, is_odk=False):
    """
    Do a POST from file with some options.  Returns a tuple of the response
    from the server and any errors.  For more flexibility, use the curl option
    """     
    up = urlparse(url)
    dict = {}
    results = None
    errors = None
    try:
        f = open(filename, "rb")
        data = f.read()
        if use_curl:
            params = [curl_command, '--request', 'POST' ]
            if is_odk == False:
                #it's legacy j2me
                params.append('--header')
                params.append('Content-type:%s' % content_type)
                params.append('--data-binary')
                params.append('@%s' % filename)
            else:
                params.append('-F')
                params.append('xml_submission_file=@%s' % filename)

            if use_chunked:
                params.append('--header')
                params.append('Transfer-encoding:chunked')
            else:
                if not is_odk:
                    params.append('--header')
                    params.append('"Content-length:%s"' % len(data))

            params.append(url)
            print params

            p = subprocess.Popen(params,
                                  stdout=PIPE,stderr=PIPE,shell=False)
            errors = p.stderr.read()
            results = p.stdout.read()
        else:
            dict["content-type"] = content_type
            dict["content-length"] = len(data)
            conn = httplib.HTTPConnection(up.netloc)
            conn.request('POST', up.path, data, dict)
            resp = conn.getresponse()
            results = resp.read()
    except Exception, e:
        errors = str(e)
    return (results,errors)