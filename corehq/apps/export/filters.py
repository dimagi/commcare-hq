from corehq.apps.es import filters as esfilters
from corehq.apps.es.cases import (
    owner,
    is_closed,
    opened_range,
    modified_range,
    user,
    closed_range,
)


class ExportFilter(object):
    """
    Abstract base class for an export filter on a single case or form property
    """

    def to_es_filter(self):
        """
        Return an ES filter representing this filter
        """
        raise NotImplementedError

    # TODO: Add another function here to be used for couch filtering


class RangeExportFilter(ExportFilter):

    def __init__(self, gt=None, gte=None, lt=None, lte=None):
        self.gt = gt
        self.gte = gte
        self.lt = lt
        self.lte = lte


class OwnerFilter(ExportFilter):
    """
    Filter on owner_id
    """
    def __init__(self, owner_id):
        self.owner_id = owner_id

    def to_es_filter(self):
        return owner(self.owner_id)


class IsClosedFilter(ExportFilter):
    """
    Filter on case closed property
    """
    def __init__(self, is_closed):
        self.is_closed = is_closed

    def to_es_filter(self):
        return is_closed(self.is_closed)


class NameFilter(ExportFilter):

    def __init__(self, case_name):
        self.case_name = case_name

    def to_es_filter(self):
        return esfilters.term('name', self.case_name)


class OpenedOnRangeFilter(RangeExportFilter):

    def to_es_filter(self):
        return opened_range(self.gt, self.gte, self.lt, self.lte)


class OpenedByFilter(ExportFilter):

    def __init__(self, opened_by):
        self.opened_by = opened_by

    def to_es_filter(self):
        # TODO: Add this to default case filters?
        return esfilters.term('opened_by', self.opened_by)


class ModifiedOnRangeFilter(RangeExportFilter):

    def to_es_filter(self):
        return modified_range(self.gt, self.gte, self.lt, self.lte)


class LastModifiedByFilter(ExportFilter):

    def __init__(self, last_modified_by):
        self.last_modified_by = last_modified_by

    def to_es_filter(self):
        return user(self.last_modified_by)


class ClosedOnRangeFilter(RangeExportFilter):

    def to_es_filter(self):
        return closed_range(self.gt, self.gte, self.lt, self.lte)


class ClosedByFilter(ExportFilter):

    def __init__(self, closed_by):
        self.closed_by = closed_by

    def to_es_filter(self):
        return esfilters.term("closed_by", self.closed_by)


# TODO: owner/modifier/closer in location/group filters

# TODO: Add form filters
