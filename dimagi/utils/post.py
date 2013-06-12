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
    return r.post(payload=data).body_string(), None


def post_unauthenticated_data(data, url):
    """
    Post basic unauthenticated data, using restkit instead of the post_data
    method.
    """
    r = Resource(url, filters=[])
    return r.post(payload=data).body_string(), None


def post_authenticated_file(filename, url, username, password):
    """
    Post basic authenticated file, using restkit
    """ 
    file = open(filename, "rb")
    try:
        return post_authenticated_data(file.read(), url, username, password)
    finally:
        file.close()


def tmpfile(*args, **kwargs):
    fd, path = tempfile.mkstemp(*args, **kwargs)
    return (os.fdopen(fd, 'w'), path)


def simple_post(data, url, content_type="text/xml", timeout=60, headers=None):
    """
    POST with a cleaner API, and return the actual HTTPResponse object, so
    that error codes can be interpreted.
    """
    default_headers = {
        "content-type": content_type,
        "content-length": len(data),
    }
    if headers:
        default_headers.update(headers)
            
    up = urlparse(url)
    if url.startswith("https"):
        Connection = httplib.HTTPSConnection
    else:
        Connection = httplib.HTTPConnection
    conn = Connection(up.netloc, timeout=timeout)
    conn.request('POST', up.path, data, default_headers)
    return conn.getresponse()



def post_data(data, url, curl_command="curl", use_curl=False, 
              content_type="text/xml", path=None, use_chunked=False, 
              is_odk=False, attachments=None):
    """
    Do a POST of data with some options.  Returns a tuple of the response
    from the server and any errors

    if it's ODK, then also process any additional attachments that are an array
    of tuples of the name and the path

    """
    attachments = attachments or []
    results = None
    errors = None

    if path is not None:
        with open(path, 'rb') as f:
            data = f.read()

    try:
        if use_curl:
            if path is None:
                tmp_file, path = tmpfile()
                with tmp_file:
                    tmp_file.write(data)
            params = [curl_command, '--request', 'POST' ]
            params.append('--insecure')
            if is_odk == False:
                #it's legacy j2me
                params.append('--header')
                params.append('Content-type:%s' % content_type)
                params.append('--data-binary')
                params.append('@%s' % path)
            else:
                params.append('-F')
                params.append('xml_submission_file=@%s' % path)


                if attachments:
                    for attach in attachments:
                        params.append('-F')
                        params.append('%s=@%s' % (attach[0], attach[1]))

            if use_chunked:
                params.append('--header')
                params.append('Transfer-encoding:chunked')
            else:
                if not is_odk:
                    params.append('--header')
                    params.append('Content-length:%s' % len(data))

            params.append(url)
            p = subprocess.Popen(params,
                                 stdout=PIPE,stderr=PIPE,shell=False)
            errors = p.stderr.read()
            results = p.stdout.read()
        else:
            results = simple_post(data, url, content_type).read()
            
    except Exception, e:
        errors = str(e)

    return results, errors


def post_file(filename, url, curl_command="curl", use_curl=False,
              content_type="text/xml"):
    """
    Do a POST from file with some options.  Returns a tuple of the response
    from the server and any errors.
    """
    return post_data(None, url, curl_command, use_curl, content_type, filename)
