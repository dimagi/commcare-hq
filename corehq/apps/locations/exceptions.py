

class LocationImportError(Exception):
    pass


class LocationConsistencyError(Exception):
    pass


class LocationBulkImportError(Exception):
    pass


class LocationBulkImportInProgressException(Exception):
    pass
