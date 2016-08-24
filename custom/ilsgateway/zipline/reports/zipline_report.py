from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.toggles import EMG_AND_REC_SMS_HANDLERS


class ZiplineReport(CustomProjectReport, GenericTabularReport, DatespanMixin):
    ajax_pagination = True

    @property
    def location_id(self):
        return self.request_params.get('location_id')

    @property
    def statuses(self):
        return self.request.GET.getlist('statuses')

    @property
    def report_config(self):
        raise NotImplementedError('Not implemented yet')

    @property
    def headers(self):
        columns = self.data_source.columns
        for column in columns:
            column.sortable = False
        return DataTablesHeader(*columns)

    @property
    def data_source(self):
        raise NotImplementedError('Not implemented yet')

    @property
    def rows(self):
        return self.data_source.get_data(self.pagination.start, self.pagination.count)

    @property
    def total_records(self):
        return self.data_source.total_count

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return domain and EMG_AND_REC_SMS_HANDLERS.enabled(domain)
