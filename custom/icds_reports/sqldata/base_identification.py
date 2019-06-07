from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.datatables import DataTablesHeader
from custom.icds_reports.utils import ICDSMixin


class BaseIdentification(ICDSMixin):

    title = '1.a Identification and Basic Information'
    slug = 'identification'
    has_sections = False
    subtitle = []
    posttitle = None

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Name', sortable=False),
            DataTablesColumn('Code', sortable=False)
        )
