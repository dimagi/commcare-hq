from django.utils.translation import ugettext_noop, ugettext_lazy
from corehq.apps.reports.filters.base import BaseReportFilter, BaseSingleOptionFilter, BaseTagsFilter
from corehq.util.queries import fast_distinct, fast_distinct_in_domain
from corehq.util.quickcache import quickcache
from phonelog.models import DeviceReportEntry


class DeviceLogTagFilter(BaseReportFilter):
    slug = "logtag"
    label = ugettext_noop("Filter Logs by Tag")
    errors_only_slug = "errors_only"
    template = "reports/filters/devicelog_tags.html"

    @property
    @quickcache(['self.domain'], timeout=10 * 60)
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


class DeviceLogDomainFilter(BaseSingleOptionFilter):
    slug = "domain"
    label = ugettext_lazy("Filter Logs by Domain")

    @property
    @quickcache([], timeout=60 * 60)
    def options(self):
        return [(d, d) for d in fast_distinct(DeviceReportEntry, 'domain')]


class DeviceLogCommCareVersionFilter(BaseTagsFilter):
    slug = "commcare_version"
    label = ugettext_lazy("Filter Logs by CommCareVersion")
    placeholder = ugettext_lazy("Enter the CommCare Version you want e.g '2.28.1'")


class BaseDeviceLogFilter(BaseReportFilter):
    slug = "logfilter"
    template = "reports/filters/devicelog_filter.html"
    field = None
    label = ugettext_noop("Filter Logs By")
    url_param_map = {'Unknown': None}

    @quickcache(['self.domain', 'self.field', 'selected'], timeout=10 * 60)
    def get_filters(self, selected):
        show_all = bool(not selected)
        values = fast_distinct_in_domain(DeviceReportEntry, self.field, self.domain)
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
