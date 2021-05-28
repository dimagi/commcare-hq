"""
Tools for FHIR Bundles
"""
from typing import Generator, Optional

from corehq.motech.requests import json_or_http_error


def get_bundle(requests, endpoint=None, *, url=None, **kwargs) -> dict:
    assert endpoint or url, 'No API endpoint or URL given'
    if endpoint:
        response = requests.get(endpoint, **kwargs)
        return json_or_http_error(response)
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
