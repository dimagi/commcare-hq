"""
GroupES
--------

For example,

.. code-block:: python

    from corehq.apps.es import GroupES

    groups = (GroupES()
              .domain(domain)
              .search_string_query(q, default_fields=['name'])
              .size(10)).values()

will give you JSON for the first 10 groups in `domain` with names matching `q`.
"""
from . import filters
from .client import ElasticDocumentAdapter
from .es_query import HQESQuery
from .transient_util import get_adapter_mapping, from_dict_with_possible_id


class GroupES(HQESQuery):
    index = 'groups'

    @property
    def builtin_filters(self):
        return [
            is_case_sharing,
            is_reporting,
            group_ids,
            not_deleted,
        ] + super(GroupES, self).builtin_filters


class ElasticGroup(ElasticDocumentAdapter):

    _index_name = "hqgroups_2017-05-29"
    type = "group"

    @property
    def mapping(self):
        return get_adapter_mapping(self)

    @classmethod
    def from_python(cls, doc):
        return from_dict_with_possible_id(doc)


def is_case_sharing(value=True):
    return filters.term("case_sharing", value)


def is_reporting(value=True):
    return filters.term("reporting", value)


def group_ids(group_ids):
    return filters.term("_id", list(group_ids))


def not_deleted():
    return filters.term("doc_type", "Group")
