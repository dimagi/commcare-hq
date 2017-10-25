import abc

from dateutil.relativedelta import relativedelta
from six import with_metaclass

from custom.icds_reports.utils import apply_exclude


class ReportDataABC(with_metaclass(abc.ABCMeta)):

    def __init__(self, location_filter_value, date=None, additional_filters=None, include_test=False):
        self.include_test = include_test
        self.date = date
        self.additional_filters = additional_filters or {}
        self.location_filter_value = location_filter_value

    @property
    def location_filter_data(self):
        return self.location_filter_value.to_dict()

    @property
    def location_level(self):
        return self.location_filter_value.location_level

    @property
    def location(self):
        return self.location_filter_value.selected_location

    @property
    def group_by(self):
        return ['%s_name' % self.location_level]

    @property
    def order_by(self):
        return '%s_name' % self.location_level

    def apply_exclude(self, queryset):
        return apply_exclude(self.location_filter_value.domain, queryset)

    @abc.abstractproperty
    def date_filter(self):
        """
        Returns:
             dict
        """
        pass

    @property
    def filters(self):
        """
        Template method

        Returns:
            dict
        """
        filters = {}
        filters.update(self.location_filter_data)
        filters.update(self.additional_filters)
        filters.update(self.date_filter)
        return filters

    @abc.abstractmethod
    def get_data(self):
        pass


class MapReportDataABC(ReportDataABC):

    @property
    def date_filter(self):
        return {
            'month': self.date
        }


class SectorReportDataABC(ReportDataABC):

    @property
    def date_filter(self):
        return {
            'month': self.date
        }


class ChartReportDataABC(ReportDataABC):

    @property
    def date_filter(self):
        three_before = self.date - relativedelta(months=3)
        return {
            'month__range': (three_before, self.date)
        }
