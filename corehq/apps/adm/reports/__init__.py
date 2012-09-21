import logging
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from corehq.apps.adm import utils
from corehq.apps.adm.dispatcher import ADMSectionDispatcher
from corehq.apps.adm.models import REPORT_SECTION_OPTIONS, ADMReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin
from dimagi.utils.couch.database import get_db

class ADMSectionView(GenericReportView):
    section_name = "Active Data Management"
    app_slug = "adm"
    dispatcher = ADMSectionDispatcher
    hide_filters = True

    # adm-specific stuff
    adm_slug = None
    
    def __init__(self, request, base_context=None, *args, **kwargs):
        self.adm_sections = dict(REPORT_SECTION_OPTIONS)
        if self.adm_slug not in self.adm_sections:
            raise ValueError("The adm_slug provided, %s, is not in the list of valid ADM report section slugs: %s." %
                             (self.adm_slug, ", ".join([key for key, val in self.adm_sections.items()]))
            )
        self.subreport_slug = kwargs.get("subreport_slug")

        super(ADMSectionView, self).__init__(request, base_context, *args, **kwargs)
        self.context['report'].update(sub_slug=self.subreport_slug)
        if self.subreport_data:
            self.name = mark_safe("""%s <small>%s</small>""" %\
                        (self.subreport_data.get('value', {}).get('name'),
                         self.adm_sections.get(self.adm_slug, "ADM Report")))

    _subreport_data = None
    @property
    def subreport_data(self):
        if self._subreport_data is None:
            self._subreport_data = dict()
        return self._subreport_data

    @property
    def show_subsection_navigation(self):
        return utils.show_adm_nav(self.domain, self.request)

    @property
    def default_report_url(self):
        return reverse('default_adm_report', args=[self.request.project])

    @classmethod
    def get_url(cls, *args, **kwargs):
        subreport = kwargs.get('subreport')
        url = super(ADMSectionView, cls).get_url(*args, **kwargs)
        return "%s%s" % (url, "%s/" % subreport if subreport else "")


class DefaultReportADMSectionView(GenericTabularReport, ADMSectionView, ProjectReportParametersMixin, DatespanMixin):
    section_name = "Active Data Management"
    app_slug = "adm"
    dispatcher = ADMSectionDispatcher

    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    hide_filters = False

    # adm-specific stuff
    adm_slug = None

    @property
    def subreport_data(self):
        if self._subreport_data is None:
            self._subreport_data = dict()
            if self.subreport_slug:
                key = ["defaults", self.adm_slug, self.subreport_slug]
                data = get_db().view("adm/all_reports",
                    reduce=False,
                    startkey=key,
                    endkey=key+[{}]
                ).first()
                if data:
                    self._subreport_data = data
        return self._subreport_data

    _adm_report = None
    @property
    def adm_report(self):
        if self._adm_report is None and self.subreport_data:
            try:
                self._adm_report = ADMReport.get(self.subreport_data.get('key')[-1])
            except Exception as e:
                logging.error("Could not fetch ADM Report: %s" % e)
        return self._adm_report

    _adm_columns = None
    @property
    def adm_columns(self):
        if self._adm_columns is None:
            if self.adm_report:
                for col in self.adm_report.columns:
                    col.set_key_kwargs(
                        project=self.domain,
                        domain=self.domain,
                        datespan=self.datespan
                    )
                self._adm_columns = self.adm_report.columns
        return self._adm_columns

    @property
    def headers(self):
        header = DataTablesHeader(DataTablesColumn("FLW Name"))
        for col in self.adm_report.columns:
            header.add_column(DataTablesColumn(col.name, help_text=col.description))
        return header

    @property
    def rows(self):
        rows = []
        for user in self.users:
            row = [self.table_cell(user.get("raw_username"),
                user.get('username_in_report'))]
            for col in self.adm_columns:
                val = col.raw_value(**user)
                row.append(self.table_cell(col.clean_value(val),
                    col.html_value(val)))
            rows.append(row)
        return rows

    @classmethod
    def override_navigation_list(cls, context):
        current_slug = context.get('report', {}).get('sub_slug')
        domain = context.get('domain')

        subreports = []
        key = ["defaults", cls.adm_slug]
        subreport_list = get_db().view("adm/all_reports",
            reduce=False,
            startkey=key,
            endkey=key+[{}]
        )
        if subreport_list:
            subreport_list = subreport_list.all()

        if not subreport_list:
            return ["""<li><span class="label">
            <i class="icon-white icon-info-sign"></i> No ADM Reports Configured</span>
            </li>"""]

        for report in subreport_list:
            key = report.get("key", [])
            entry = report.get("value", {})
            report_slug = key[-2]
            if cls.show_subreport_in_navigation(report_slug):
                subreports.append("""<li%(active_class)s>
                <a href="%(url)s" title="%(description)s">%(name)s</a>
                </li>""" % dict(
                    active_class=' class="active"' if current_slug == report_slug else "",
                    url=cls.get_url(domain, subreport=report_slug),
                    description=entry.get('description', ''),
                    name=entry.get('name', 'Untitled Report')
                ))
        return subreports

    @classmethod
    def show_subreport_in_navigation(cls, report_slug):
        return True

