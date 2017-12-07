from __future__ import absolute_import
import os
import subprocess
import tempfile
from subprocess import PIPE
import requests
from zeep import Client, Transport
from zeep.cache import InMemoryCache
import six


def tmpfile(*args, **kwargs):
    fd, path = tempfile.mkstemp(*args, **kwargs)
    return (os.fdopen(fd, 'w'), path)


def simple_post(data, url, content_type="text/xml", timeout=60, headers=None, auth=None, verify=None):
    """
    POST with a cleaner API, and return the actual HTTPResponse object, so
    that error codes can be interpreted.
    """
    if isinstance(data, six.text_type):
        data = data.encode('utf-8')  # can't pass unicode to http request posts
    default_headers = requests.structures.CaseInsensitiveDict({
        "content-type": content_type,
        "content-length": len(data),
    })
    if headers:
        default_headers.update(headers)
    kwargs = {
        "headers": default_headers,
        "timeout": timeout,
    }
    if auth:
        kwargs["auth"] = auth

    if verify is not None:
        kwargs["verify"] = verify

    return requests.post(url, data, **kwargs)


def get_SOAP_client(url, verify=True):
    # http://docs.python-zeep.org/en/master/transport.html#ssl-verification
    # Disable SSL cert verification meanwhile a better way is found
    session = requests.Session()
    session.verify = verify
    transport = Transport(cache=InMemoryCache(), session=session)
    return Client(url, transport=transport)


def perform_SOAP_operation(data, url, operation, verify=True):
    client = get_SOAP_client(url, verify)
    # for just response message use
    # with client.options(raw_response=False) # explicitly set it to avoid caching mysteries
    #     return client.service[operation](**data)
    with client.options(raw_response=True):
        return client.service[operation](**data)


def parse_SOAP_response(url, operation, response, verify=True):
    # parse the xml content on response object to return just the message
    client = get_SOAP_client(url, verify)
    binding = client.service[operation]._proxy._binding
    return binding.process_reply(client, binding.get(operation), response)


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
                                 stdout=PIPE, stderr=PIPE, shell=False)
            errors = p.stderr.read()
            results = p.stdout.read()
        else:
            results = simple_post(data, url, content_type).read()
            
    except Exception as e:
        errors = str(e)

    return results, errors


def post_file(filename, url, curl_command="curl", use_curl=False,
              content_type="text/xml"):
    """
    Do a POST from file with some options.  Returns a tuple of the response
    from the server and any errors.
    """
    return post_data(None, url, curl_command, use_curl, content_type, filename)
