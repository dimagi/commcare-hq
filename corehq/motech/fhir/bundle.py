"""
Tools for FHIR Bundles

For more information about Bundles, including examples, see the
`FHIR reference <https://www.hl7.org/fhir/bundle.html>`_.

"""
from typing import Generator, Optional

from corehq.motech.requests import json_or_http_error


def get_bundle(requests, endpoint=None, *, url=None, **kwargs) -> dict:
    """
    Sends a GET request to an API endpoint or a URL and returns the
    response JSON.

    ``endpoint`` is a relative URL, e.g. 'Patient/'. ``url`` is an
    absolute URL, e.g. 'https://example.com/fhir/Patient/'

    """
    assert endpoint or url, 'No API endpoint or URL given'
    if endpoint:
        response = requests.get(endpoint, **kwargs)
    else:
        # Use requests.send_request() so that `url` is not appended to
        # `requests.base_url`
        response = requests.send_request('GET', url, **kwargs)
    return json_or_http_error(response)


def iter_bundle(bundle: dict) -> Generator:
    """
    Iterate the entries in a bundle

    >>> bundle = {
    ...     'entry': [
    ...         {'resource': {'name': 'foo'}},
    ...         {'resource': {'name': 'bar'}},
    ...         {'resource': {'name': 'baz'}},
    ...     ]
    ... }
    >>> list(iter_bundle(bundle))
    [{'name': 'foo'}, {'name': 'bar'}, {'name': 'baz'}]

    """
    for entry in bundle.get('entry', []):
        if 'resource' in entry:
            yield entry['resource']


def get_next_url(bundle: dict) -> Optional[str]:
    """
    Returns the URL for the next page of a paginated ``bundle``.

    >>> bundle = {
    ...     'link': [
    ...         {'relation': 'self', 'url': 'https://example.com/page/2'},
    ...         {'relation': 'next', 'url': 'https://example.com/page/3'},
    ...         {'relation': 'previous', 'url': 'https://example.com/page/1'},
    ...     ]
    ... }
    >>> get_next_url(bundle)
    'https://example.com/page/3'

    >>> bundle = {
    ...     'link': [
    ...         {'relation': 'self', 'url': 'https://example.com/page/1'},
    ...     ]
    ... }
    >>> type(get_next_url(bundle))
    <class 'NoneType'>

    """
    if 'link' in bundle:
        for link in bundle['link']:
            if link['relation'] == 'next':
                return link['url']
