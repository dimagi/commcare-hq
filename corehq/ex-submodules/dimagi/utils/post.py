import requests
import six


def simple_post(data, url, content_type="text/xml", timeout=60, headers=None, auth=None, verify=None):
    """
    POST with a cleaner API, and return the actual HTTPResponse object, so
    that error codes can be interpreted.
    """
    if isinstance(data, six.text_type):
        data = data.encode('utf-8')  # can't pass unicode to http request posts
    default_headers = requests.structures.CaseInsensitiveDict({
        "content-type": content_type,
        "content-length": str(len(data)),
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
