from urlparse import urlparse
import httplib

def post_data(data, url, submit_time=None, content_type = "text/xml"):
    """
    Do a POST from file with some options.  Returns a tuple of the response
    from the server and any errors.
    """
    up = urlparse(url)
    headers = {}
    results = None
    errors = None
    try:
        headers["content-type"] = content_type
        headers["content-length"] = len(data)
        if submit_time:
            headers["x-submit-time"] = submit_time
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, data, headers)
        resp = conn.getresponse()
        results = resp.read()
    except Exception, e:
        errors = str(e)
    return (results,errors)