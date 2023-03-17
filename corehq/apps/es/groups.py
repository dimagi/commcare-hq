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
from copy import copy

from . import filters
from .client import ElasticDocumentAdapter, create_document_adapter
from .es_query import HQESQuery
from .index.settings import IndexSettingsKey
from .transient_util import get_adapter_mapping


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

    settings_key = IndexSettingsKey.GROUPS

    @property
    def mapping(self):
        return get_adapter_mapping(self)

    @classmethod
    def from_python(cls, group):
        from corehq.apps.groups.models import Group
        if isinstance(group, Group):
            group_dict = group.to_json()
        elif isinstance(group, dict):
            group_dict = copy(group)
        else:
            raise TypeError(f"Unknown type {type(group)}")
        return group_dict.pop('_id'), group_dict


group_adapter = create_document_adapter(
    ElasticGroup,
    "hqgroups_2017-05-29",
    "group",
)


def is_case_sharing(value=True):
    return filters.term("case_sharing", value)


def is_reporting(value=True):
    return filters.term("reporting", value)


def group_ids(group_ids):
    return filters.term("_id", list(group_ids))


def not_deleted():
    return filters.term("doc_type", "Group")
