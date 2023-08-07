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
from .client import ElasticDocumentAdapter, create_document_adapter
from .const import (
    HQ_GROUPS_INDEX_CANONICAL_NAME,
    HQ_GROUPS_INDEX_NAME,
    HQ_GROUPS_SECONDARY_INDEX_NAME,
)
from .es_query import HQESQuery
from .index.settings import IndexSettingsKey


class GroupES(HQESQuery):
    index = HQ_GROUPS_INDEX_CANONICAL_NAME

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
    canonical_name = HQ_GROUPS_INDEX_CANONICAL_NAME

    @property
    def mapping(self):
        from .mappings.group_mapping import GROUP_MAPPING
        return GROUP_MAPPING

    @property
    def model_cls(self):
        from corehq.apps.groups.models import Group
        return Group


group_adapter = create_document_adapter(
    ElasticGroup,
    HQ_GROUPS_INDEX_NAME,
    "group",
    secondary=HQ_GROUPS_SECONDARY_INDEX_NAME,
)


def is_case_sharing(value=True):
    return filters.term("case_sharing", value)


def is_reporting(value=True):
    return filters.term("reporting", value)


def group_ids(group_ids):
    return filters.term("_id", list(group_ids))


def not_deleted():
    return filters.term("doc_type", "Group")
