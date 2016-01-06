from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseReportFilter
from corehq.util.queries import fast_distinct
from phonelog.models import DeviceReportEntry


class DeviceLogTagFilter(BaseReportFilter):
    # todo: clean this up
    slug = "logtag"
    label = ugettext_noop("Filter Logs by Tag")
    errors_only_slug = "errors_only"
    template = "reports/filters/bootstrap2/devicelog_tags.html"

    @property
    def filter_context(self):
        errors_only = bool(self.request.GET.get(self.errors_only_slug, False))
        selected_tags = self.request.GET.getlist(self.slug)
        show_all = bool(not selected_tags)
        values = fast_distinct(DeviceReportEntry, 'type')
        tags = [{
            'name': value,
            'show': bool(show_all or value in selected_tags)
        } for value in values]
        context = {
            'errors_only_slug': self.errors_only_slug,
            'default_on': show_all,
            'logtags': tags,
            'errors_css_id': 'device_log_errors_only_checkbox',
            self.errors_only_slug: errors_only,
        }
        return context


class BaseDeviceLogFilter(BaseReportFilter):
    # todo: make this better
    slug = "logfilter"
    template = "reports/filters/bootstrap2/devicelog_filter.html"
    field = None
    label = ugettext_noop("Filter Logs By")
    url_param_map = {'Unknown': None}

    def get_filters(self, selected):
        show_all = bool(not selected)
        values = (DeviceReportEntry.objects.filter(domain=self.domain)
                  .values(self.field).distinct()
                  .values_list(self.field, flat=True))
        return [{
            'name': self.value_to_param(value),
            'show': bool(show_all or value in selected)
        } for value in values]

    @property
    def filter_context(self):
        selected = self.get_selected(self.request)
        return {
            'filters': self.get_filters(selected),
            'default_on': bool(not selected),
        }

    @classmethod
    def get_selected(cls, request):
        return [cls.param_to_value(param)
                for param in request.GET.getlist(cls.slug)]

    @classmethod
    def param_to_value(cls, param):
        return cls.url_param_map.get(param, param)

    @classmethod
    def value_to_param(cls, value):
        for param, value_ in cls.url_param_map.items():
            if value_ == value:
                return param
        return value


class DeviceLogUsersFilter(BaseDeviceLogFilter):
    slug = "loguser"
    label = ugettext_noop("Filter Logs by Username")
    field = 'username'


class DeviceLogDevicesFilter(BaseDeviceLogFilter):
    slug = "logdevice"
    label = ugettext_noop("Filter Logs by Device")
    field = 'device_id'
