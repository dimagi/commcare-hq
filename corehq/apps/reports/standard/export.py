from django.utils.translation import ugettext_noop, ugettext_lazy
from corehq.apps.reports.dbaccessors import stale_get_export_count
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher

from corehq.apps.data_interfaces.interfaces import DataInterface
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.models import FormExportSchema
from corehq.apps.reports.util import datespan_from_beginning
from couchexport.models import Format


class ExportReport(DataInterface, ProjectReportParametersMixin):
    """
        Base class for export reports.
    """
    flush_layout = True
    dispatcher = DataInterfaceDispatcher

    @property
    def custom_bulk_export_format(self):
        return Format.XLS_2007

    @property
    def report_context(self):
        return dict(
            custom_bulk_export_format=self.custom_bulk_export_format,
            saved_exports=self.get_saved_exports(),
            timezone=self.timezone,
            get_filter_params=self.get_filter_params(),
        )


class FormExportReportBase(ExportReport, DatespanMixin):
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    @memoized
    def get_saved_exports(self):
        from corehq.apps.export.views import user_can_view_deid_exports
        exports = FormExportSchema.get_stale_exports(self.domain)
        if not user_can_view_deid_exports(self.domain, self.request.couch_user):
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain, self.timezone)

    def get_filter_params(self):
        params = self.request.GET.copy()
        if self.datespan.startdate_display:  # when no forms have been submitted to a domain, this defaults to None
            params['startdate'] = self.datespan.startdate_display
        params['enddate'] = self.datespan.enddate_display
        return params

    @classmethod
    def get_subpages(self):
        from corehq.apps.export.views import CreateCustomFormExportView, EditCustomFormExportView
        return [
            {
                'title': CreateCustomFormExportView.page_title,
                'urlname': CreateCustomFormExportView.urlname,
            },
            {
                'title': EditCustomFormExportView.page_title,
                'urlname': EditCustomFormExportView.urlname,
            },
        ]


class DeidExportReport(FormExportReportBase):
    slug = 'deid_export'
    name = ugettext_lazy("De-Identified Export")
    report_template_path = 'reports/reportdata/form_deid_export.html'

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return stale_get_export_count(domain) > 0

    def get_saved_exports(self):
        return filter(lambda export: export.is_safe, super(DeidExportReport, self).get_saved_exports())

    @property
    def report_context(self):
        context = super(DeidExportReport, self).report_context
        context.update(
            ExcelExportReport_name=ugettext_noop("Export Forms"),
            is_deid_form_report=True
        )
        return context

    def get_filter_params(self):
        params = super(DeidExportReport, self).get_filter_params()
        params['deid'] = 'true'
        return params

    @classmethod
    def get_subpages(self):
        return []
