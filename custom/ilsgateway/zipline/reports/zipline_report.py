from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin


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
    def data_source(self):
        raise NotImplementedError('Not implemented yet')

    @property
    def rows(self):
        return self.data_source.get_data(self.pagination.start, self.pagination.count)
