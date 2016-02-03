from corehq.apps.es.cases import owner, is_closed


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

# etc...
