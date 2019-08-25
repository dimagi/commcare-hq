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
from .es_query import HQESQuery
from . import filters


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


def is_case_sharing(value=True):
    return filters.term("case_sharing", value)


def is_reporting(value=True):
    return filters.term("reporting", value)


def group_ids(group_ids):
    return filters.term("_id", list(group_ids))


def not_deleted():
    return filters.term("doc_type", "Group")
