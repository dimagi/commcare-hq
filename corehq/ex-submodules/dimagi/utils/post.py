from requests.structures import CaseInsensitiveDict

from corehq.motech.requests import Requests


def simple_post(domain, url, data, *, headers, auth, verify,
                timeout=60, notify_addresses=None, payload_id=None):
    """
    POST with a cleaner API, and return the actual HTTPResponse object, so
    that error codes can be interpreted.
    """
    default_headers = CaseInsensitiveDict({
        "content-type": "text/xml",
        "content-length": str(len(data)),
    })
    default_headers.update(headers)
    kwargs = {
        "headers": default_headers,
        "timeout": timeout,
    }
    requests = Requests(
        domain,
        base_url='',
        username=None,
        password=None,
        verify=verify,
        notify_addresses=notify_addresses,
        payload_id=payload_id,
    )
    # Use ``send_request()`` instead of ``post()`` to pass ``auth``.
    return requests.send_request('POST', url, data=data, auth=auth, **kwargs)
