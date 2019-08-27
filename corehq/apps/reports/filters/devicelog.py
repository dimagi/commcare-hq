from django.urls import reverse
from django.utils.translation import ugettext_lazy
from corehq.apps.reports.filters.base import (
    BaseReportFilter, BaseSingleOptionFilter, BaseTagsFilter, BaseMultipleOptionFilter
)
from corehq.util.queries import fast_distinct, fast_distinct_in_domain
from corehq.util.quickcache import quickcache
from phonelog.models import DeviceReportEntry


class DeviceLogTagFilter(BaseReportFilter):
    slug = "logtag"
    label = ugettext_lazy("Filter Logs by Tag")
    errors_only_slug = "errors_only"
    template = "reports/filters/devicelog_tags.html"

    @quickcache(['self.domain'], timeout=10 * 60)
    def _all_values(self):
        return fast_distinct_in_domain(DeviceReportEntry, 'type', self.domain)

    @property
    def filter_context(self):
        errors_only = bool(self.request.GET.get(self.errors_only_slug, False))
        selected_tags = self.request.GET.getlist(self.slug)
        show_all = bool(not selected_tags)
        values = self._all_values()
        tags = [{
            'name': value,
            'show': bool(show_all or value in selected_tags)
        } for value in values]
        context = {
            'errors_only_slug': self.errors_only_slug,
            'default_on': show_all,
            'logtags': tags,
            'errors_css_id': 'device-log-errors-only-checkbox',
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


class BaseDeviceLogFilter(BaseMultipleOptionFilter):
    slug = "logfilter"
    field = None
    label = ugettext_lazy("Filter Logs By")
    url_param_map = {'Unknown': None}
    endpoint = None

    @property
    def filter_context(self):
        selected = self.get_selected(self.request)
        url = reverse(self.endpoint, args=[self.domain])
        return {
            'default_on': bool(not selected),
            'endpoint': url,
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
    label = ugettext_lazy("Filter Logs by Username")
    field = 'username'
    endpoint = 'device_log_users'


class DeviceLogDevicesFilter(BaseDeviceLogFilter):
    slug = "logdevice"
    label = ugettext_lazy("Filter Logs by Device")
    field = 'device_id'
    endpoint = 'device_log_ids'
