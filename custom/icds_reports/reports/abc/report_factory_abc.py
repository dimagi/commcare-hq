import abc

from six import with_metaclass


class ReportFactoryABC(with_metaclass(abc.ABCMeta)):

    @abc.abstractmethod
    def get_map_report_instance(self, location_filter_value, date, **kwargs):
        pass

    @abc.abstractmethod
    def get_sector_report_instance(self, location_filter_value, date, **kwargs):
        pass

    @abc.abstractmethod
    def get_chart_report_instance(self, location_filter_value, date, **kwargs):
        pass
