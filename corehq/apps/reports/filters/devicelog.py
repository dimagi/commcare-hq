from django.urls import reverse
from django.utils.translation import gettext_lazy

from phonelog.models import DeviceReportEntry

from corehq.apps.reports.filters.base import (
    BaseMultipleOptionFilter,
    BaseReportFilter,
)
from corehq.apps.reports.util import DatatablesServerSideParams
from corehq.util.queries import fast_distinct_in_domain
from corehq.util.quickcache import quickcache


class DeviceLogTagFilter(BaseReportFilter):
    slug = "logtag"
    label = gettext_lazy("Filter Logs by Tag")
    errors_only_slug = "errors_only"
    template = "reports/filters/bootstrap3/devicelog_tags.html"

    @quickcache(['self.domain'], timeout=10 * 60)
    def _all_values(self):
        return fast_distinct_in_domain(DeviceReportEntry, 'type', self.domain)

    @property
    def filter_context(self):
        errors_only = bool(DatatablesServerSideParams.get_value_from_request(
            self.request, self.errors_only_slug, False
        ))
        selected_tags = DatatablesServerSideParams.get_value_from_request(
            self.request, self.slug, as_list=True
        )
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


class BaseDeviceLogFilter(BaseMultipleOptionFilter):
    slug = "logfilter"
    field = None
    label = gettext_lazy("Filter Logs By")
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
                for param in DatatablesServerSideParams.get_value_from_request(request, cls.slug, as_list=True)]

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
    label = gettext_lazy("Filter Logs by Username")
    field = 'username'
    endpoint = 'device_log_users'


class DeviceLogDevicesFilter(BaseDeviceLogFilter):
    slug = "logdevice"
    label = gettext_lazy("Filter Logs by Device")
    field = 'device_id'
    endpoint = 'device_log_ids'
