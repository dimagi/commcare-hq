from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport


# this is a quick sketch of a possible way to start decoupling report rendering
# from data. it seemed okay but not good enough to push to core without some
# more cleanup / more featured functionality.
class DataProvider(object):

    def headers(self):
        return DataTablesHeader()

    def rows(self):
        return []

class ComposedTabularReport(GenericTabularReport):

    data_provider = DataProvider()

    is_bootstrap3 = True

    @property
    def headers(self):
        return self.data_provider.headers()

    @property
    def rows(self):
        return self.data_provider.rows()
