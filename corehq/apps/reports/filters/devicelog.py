from django.utils.translation import ugettext_noop
from dimagi.utils.couch.database import get_db
from corehq.apps.reports.filters.base import BaseReportFilter
from phonelog.models import DeviceReportEntry
import settings


class DeviceLogTagFilter(BaseReportFilter):
    # todo: clean this up
    slug = "logtag"
    label = ugettext_noop("Filter Logs by Tag")
    errors_only_slug = "errors_only"
    template = "reports/filters/devicelog_tags.html"

    @property
    def filter_context(self):
        errors_only = bool(self.request.GET.get(self.errors_only_slug, False))
        selected_tags = self.request.GET.getlist(self.slug)
        show_all = bool(not selected_tags)
        tags = [dict(name=l['type'],
                    show=bool(show_all or l['type'] in selected_tags))
                    for l in DeviceReportEntry.objects.values('type').distinct()]
        context = {
            'errors_only_slug': self.errors_only_slug,
            'default_on': show_all,
            'logtags': tags,
            'errors_css_id': 'device_log_errors_only_checkbox'
        }
        context[self.errors_only_slug] = errors_only
        return context


class BaseDeviceLogFilter(BaseReportFilter):
    # todo: make this better
    slug = "logfilter"
    template = "reports/filters/devicelog_filter.html"
    field = None
    label = ugettext_noop("Filter Logs By")

    def get_filters(self, selected):
        show_all = bool(not selected)
        it = DeviceReportEntry.objects.filter(domain__exact=self.domain).values(self.field).distinct()
        return [dict(name=f[self.field],
                    show=bool(show_all or f[self.field] in selected))
                    for f in it]

    @property
    def filter_context(self):
        selected = self.request.GET.getlist(self.slug)
        return {
            'filters': self.get_filters(selected),
            'default_on': bool(not selected)
        }


class DeviceLogUsersFilter(BaseDeviceLogFilter):
    slug = "loguser"
    label = ugettext_noop("Filter Logs by Username")
    field = 'username'


class DeviceLogDevicesFilter(BaseDeviceLogFilter):
    slug = "logdevice"
    label = ugettext_noop("Filter Logs by Device")
    field = 'device_id'
