from __future__ import absolute_import
from __future__ import unicode_literals


class ReportNotFoundError(Exception):
    pass


class EndpointNotFoundError(Exception):
    pass


class ColumnFilterNotFound(Exception):
    pass


class ReportFilterNotFound(Exception):
    pass
