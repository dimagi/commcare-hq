from abc import ABC, abstractmethod

from django.utils.translation import gettext_lazy

from corehq.apps.case_search.const import INDEXED_METADATA_BY_KEY
from corehq.apps.case_search.utils import get_case_id_sort_block
from corehq.apps.es.case_search import wrap_case_search_hit
from corehq.apps.reports.standard.cases.data_sources import SafeCaseDisplay
from corehq.util.timezones.utils import get_timezone


class BaseElasticRecord(ABC):

    def __init__(self, record, request, **kwargs):
        self.record = record
        self.request = request

    def __repr__(self):
        return f"{self.__class__.__name__}(record={str(self.record)})"

    def __getitem__(self, item):
        raise NotImplementedError("please implement __getitem__")

    @property
    @abstractmethod
    def verbose_name(self):
        """
        The full (singular) human-friendly name for the data.

        :return: string
        """

    @property
    @abstractmethod
    def verbose_name_plural(self):
        """
        The full (plural) human-friendly name for the data.

        :return: string
        """

    @staticmethod
    def get_sorted_query(query, accessors):
        """
        This should return a sorted version of the query passed into it based on
        the sorting specified by `accessors`.

        Arguments:
            query (ESQuery subclass):
                the query we want to apply sorting to

            accessors (list of `OrderBy` instances from django_tables2):
                iterate through the list to an `accessor` (`OrderBy`) with the
                following relevant properties:
                    `accessor.bare`: the accessor as defined by the table column
                    `accessor.is_descending`: (boolean) True if the sort order is descending
        :return: an instance of ESQuery (same subclass as the query passed in)
        """
        raise NotImplementedError("please implement `get_sorted_query`")


class CaseSearchElasticRecord(BaseElasticRecord):
    verbose_name = gettext_lazy("case")
    verbose_name_plural = gettext_lazy("cases")

    def __init__(self, record, request, **kwargs):
        record = SafeCaseDisplay(
            wrap_case_search_hit(record),
            get_timezone(request, request.domain)
        )
        super().__init__(record, request, **kwargs)

    def __getitem__(self, item):
        return self.record.get(item)

    @staticmethod
    def get_sorted_query(query, accessors):
        for accessor in accessors:
            try:
                meta_property = INDEXED_METADATA_BY_KEY[accessor.bare]
                if meta_property.key == '@case_id':
                    # This condition is added because ES 5 does not allow sorting on _id.
                    #  When we will have case_id in root of the document, this should be removed.
                    query.es_query['sort'] = get_case_id_sort_block(accessor.is_descending)
                    return query
                query = query.sort(meta_property.es_field_name, desc=accessor.is_descending)
            except KeyError:
                query = query.sort_by_case_property(accessor.bare, desc=accessor.is_descending)
        return query
