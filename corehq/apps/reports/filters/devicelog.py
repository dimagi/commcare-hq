from django.utils.translation import ugettext_noop
from dimagi.utils.couch.database import get_db
from corehq.apps.reports.filters.base import BaseReportFilter
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
        data = get_db().view('phonelog/device_log_tags',
                             group=True,
                             stale=settings.COUCH_STALE_QUERY)
        tags = [dict(name=item['key'],
                    show=bool(show_all or item['key'] in selected_tags))
                    for item in data]
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
    view = "phonelog/devicelog_data"
    label = ugettext_noop("Filter Logs By")

    @property
    def filter_context(self):
        selected = self.request.GET.getlist(self.slug)
        show_all = bool(not selected)

        data = get_db().view(
            self.view,
            startkey = [self.domain],
            endkey = [self.domain, {}],
            group=True,
            stale=settings.COUCH_STALE_QUERY,
        )
        filters = [dict(name=item['key'][-1],
                    show=bool(show_all or item['key'][-1] in selected))
                        for item in data]
        return {
            'filters': filters,
            'default_on': show_all
        }


class DeviceLogUsersFilter(BaseDeviceLogFilter):
    slug = "loguser"
    view = "phonelog/devicelog_data_users"
    label = ugettext_noop("Filter Logs by Username")


class DeviceLogDevicesFilter(BaseDeviceLogFilter):
    slug = "logdevice"
    view = "phonelog/devicelog_data_devices"
    label = ugettext_noop("Filter Logs by Device")
