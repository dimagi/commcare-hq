from typing import Generator, List, Type, Union

import attr
from jsonpath_ng.ext.parser import parse as jsonpath_parse

from corehq.motech.requests import Requests
from corehq.motech.utils import simplify_list

from .const import SYSTEM_URI_CASE_ID
from .bundle import get_bundle, get_next_url, iter_bundle


class ResourceSearcher:
    """
    Searches a remote FHIR API in increasingly broad terms.

    Used in conjunction with ResourceMatcher to find matching resources.
    """
    # A list of searches, and for each one, the list of search params to
    # filter by
    search_search_params: List[List['SearchParam']]

    def __init__(self, requests: Requests, resource: dict):
        self.requests = requests
        self.resource = resource

    def iter_searches(self) -> Generator['Search', None, None]:
        # Separate out searches so that the caller can stop if they find
        # the resource they need with a narrow search, before trying a
        # broader search.
        return (Search(self.requests, self.resource, search_params)
                for search_params in self.search_search_params)


class Search:
    """
    A search, based on a list of ``SearchParam``s to filter by.
    """

    def __init__(
        self,
        requests: Requests,
        resource: dict,
        search_params: List['SearchParam'],
    ):
        self.requests = requests
        self.resource = resource
        self.search_params = search_params

    def iter_candidates(self) -> Generator:
        """
        Iterates the candidates returned by the search.
        """
        for params in self._get_request_params():
            # One search usually involves one dictionary of request
            # params, but can involve many. e.g. Searching for a
            # patient by each of their given names is done with a series
            # of requests.
            endpoint = f"{self.resource['resourceType']}/"
            searchset_bundle = get_bundle(self.requests, endpoint, params=params)
            while True:
                yield from iter_bundle(searchset_bundle)
                url = get_next_url(searchset_bundle)
                if url:
                    searchset_bundle = get_bundle(self.requests, url=url)
                else:
                    break

    def _get_request_params(self) -> List[dict]:
        request_params = [{}]
        for sp in self.search_params:
            value = sp.param.get_value(self.resource)
            if value is None:
                continue
            elif isinstance(value, list):
                request_params = multiply(request_params, sp.param_name, value)
            else:
                update_all(request_params, sp.param_name, value)
        return request_params


class ParamHelper:
    """
    Formats search parameter values.

    If ``get_value()`` returns a list of values, ``Search.iter_candidates()``
    will send a request for each value.
    """

    def __init__(self, jsonpath: str):
        self.jsonpath = jsonpath_parse(jsonpath)

    def get_value(self, resource: dict) -> Union[None, str, List[str]]:
        value = simplify_list([x.value for x in self.jsonpath.find(resource)])
        return None if value is None else self.prepare_value(value)

    @staticmethod
    def prepare_value(value) -> Union[str, List[str]]:
        if isinstance(value, list):
            return [str(v) for v in value]
        return str(value)


class GivenName(ParamHelper):

    @staticmethod
    def prepare_value(value):
        """
        ``value`` is a given name or a list of given names. Returns a
        string by joining given names with " ".
        """
        if isinstance(value, list):
            return ' '.join(value)
        return value


class EachUniqueValue(ParamHelper):

    @staticmethod
    def prepare_value(value):
        """
        Returns a list of unique values, or the value if there is only
        one.
        """
        if isinstance(value, list):
            if value and isinstance(value[0], list):
                set_ = {item for list_ in value for item in list_}
                return simplify_list(list(set_))
            return simplify_list(list(set(value)))
        return value


@attr.s(auto_attribs=True)
class SystemCode:
    """
    A search parameter value that is made up of a system and a code.

    e.g. To search by case ID, we use the "identifier" param, and
    provide both the case ID under "code" and a URI for CommCare under
    "system".
    """
    system: str
    code: str

    def __str__(self):
        if self.system and self.code:
            return f'{self.system}|{self.code}'
        return self.system or self.code or ''


class SystemCodeParam(ParamHelper):

    @staticmethod
    def prepare_value(value):
        """
        ``value`` is a dictionary with "system" and "value" keys.
        """
        system_code = SystemCode(system=value['system'], code=value['value'])
        return str(system_code)


@attr.s(auto_attribs=True)
class SearchParam:
    """
    SearchParam has a ``jsonpath`` that specifies where to get the
    search parameter's value, and an optional ``ParamHelper`` to format
    the value for use as a search parameter.
    """
    param_name: str  # e.g. "given"
    jsonpath: str  # e.g. "$.name[0].given"
    param_class: Type[ParamHelper] = ParamHelper

    @property
    def param(self):
        return self.param_class(self.jsonpath)


class PatientSearcher(ResourceSearcher):
    search_search_params = [
        # First search: Case name and case ID
        [
            SearchParam('name', '$.name[0].text'),
            SearchParam(
                param_name='identifier',
                jsonpath=f"$.identifier[?system='{SYSTEM_URI_CASE_ID}']",
                param_class=SystemCodeParam,
            ),
        ],

        # Second search: Personal details
        [
            SearchParam('given', '$.name[0].given', GivenName),
            SearchParam('family', '$.name[0].family'),
            SearchParam('gender', '$.gender'),
            SearchParam('birthdate', '$.birthDate'),
            SearchParam('email', "$.telecom[?system='email'].value",
                        EachUniqueValue),
            SearchParam('phone', "$.telecom[?system='phone'].value",
                        EachUniqueValue),
            SearchParam('address-country', '$.address[*].country',
                        EachUniqueValue),
            SearchParam('address-state', '$.address[*].state',
                        EachUniqueValue),
            SearchParam('address-city', '$.address[*].city',
                        EachUniqueValue),
        ],

        # Third time's the charm: Broad searches by names
        [
            SearchParam('given', '$.name[*].given', EachUniqueValue),
            SearchParam('family', '$.name[*].family'),
        ],
    ]


def update_all(dicts: List[dict], key, value):
    for dict_ in dicts:
        dict_[key] = value


def multiply(dicts: List[dict], key, values: list) -> List[dict]:
    """
    Duplicates and updates ``dicts`` for each value in ``values``.

    >>> multiply([{'foo': 1}], key='bar', values=[2, 3])
    [{'foo': 1, 'bar': 2}, {'foo': 1, 'bar': 3}]

    """
    return [
        {**dict_, **{key: value}}
        for dict_ in dicts
        for value in values
    ]
