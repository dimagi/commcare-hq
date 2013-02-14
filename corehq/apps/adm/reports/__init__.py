import logging
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from corehq.apps.adm.dispatcher import ADMSectionDispatcher
from corehq.apps.adm.models import REPORT_SECTION_OPTIONS, ADMReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop

class ADMSectionView(GenericReportView):
    section_name = ugettext_noop("Active Data Management")
    app_slug = "adm"
    dispatcher = ADMSectionDispatcher
    hide_filters = True
    emailable = True


    # adm-specific stuff
    adm_slug = None
    
    def __init__(self, request, base_context=None, domain=None, **kwargs):
        self.adm_sections = dict(REPORT_SECTION_OPTIONS)
        if self.adm_slug not in self.adm_sections:
            raise ValueError("The adm_slug provided, %s, is not in the list of valid ADM report section slugs: %s." %
                             (self.adm_slug, ", ".join([key for key, val in self.adm_sections.items()]))
            )
        self.subreport_slug = kwargs.get("subreport_slug")

        super(ADMSectionView, self).__init__(request, base_context, domain=domain, **kwargs)
        self.context['report'].update(sub_slug=self.subreport_slug)
        if self.subreport_data:
            self.name = mark_safe("""%s <small>%s</small>""" %\
                        (self.subreport_data.get('value', {}).get('name'),
                         self.adm_sections.get(self.adm_slug, _("ADM Report"))))

    @property
    def subreport_data(self):
        raise NotImplementedError

    @property
    def default_report_url(self):
        return reverse('default_adm_report', args=[self.request.project])

    @classmethod
    def get_url(cls, domain=None, render_as=None, **kwargs):
        subreport = kwargs.get('subreport')
        url = super(ADMSectionView, cls).get_url(domain=domain, render_as=render_as, **kwargs)
        return "%s%s" % (url, "%s/" % subreport if subreport else "")


class DefaultReportADMSectionView(GenericTabularReport, ADMSectionView, ProjectReportParametersMixin, DatespanMixin):

    section_name = ugettext_noop("Active Data Management")
    app_slug = "adm"
    dispatcher = ADMSectionDispatcher
    fix_left_col = True

    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    hide_filters = False

    # adm-specific stuff
    adm_slug = None

    @property
    @memoized
    def subreport_data(self):
        default_subreport = ADMReport.get_default(self.subreport_slug, domain=self.domain,
                section=self.adm_slug, wrap=False)
        if default_subreport is None:
            return dict()
        return default_subreport

    @property
    @memoized
    def adm_report(self):
        if self.subreport_data:
            try:
                adm_report = ADMReport.get_correct_wrap(self.subreport_data.get('key')[-1])
                adm_report.set_domain_specific_values(self.domain)
                return adm_report
            except Exception as e:
                logging.error("Could not fetch ADM Report: %s" % e)
        return None

    @property
    @memoized
    def adm_columns(self):
        if self.adm_report:
            column_config = self.report_column_config
            if not isinstance(column_config, dict):
                ValueError('report_column_config should return a dict')
            for col in self.adm_report.columns:
                col.set_report_values(**column_config)
            return self.adm_report.columns
        return []

    @property
    def headers(self):
        if self.subreport_slug is None:
            raise ValueError("Cannot render this report. A subreport_slug is required.")
        header = DataTablesHeader(DataTablesColumn(_("FLW Name")))
        for col in self.adm_report.columns:
            sort_type = DTSortType.NUMERIC if hasattr(col, 'returns_numerical') and col.returns_numerical else None
            help_text = _(col.description) if col.description else None
            header.add_column(DataTablesColumn(_(col.name), sort_type=sort_type, help_text=help_text))
        header.custom_sort = self.adm_report.default_sort_params
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
        self.statistics_rows = [["Total"], ["Average"]]
        for ind, col in enumerate(self.adm_columns):
            column_data = [row[1+ind] for row in rows]
            self.statistics_rows[0].append(col.calculate_totals(column_data))
            self.statistics_rows[1].append(col.calculate_averages(column_data))
        return rows

    @property
    def report_column_config(self):
        """
            Should return a dict of values important for rendering the ADMColumns in this report.
        """
        return dict(
            domain=self.domain,
            datespan=self.datespan
        )

    @classmethod
    def override_navigation_list(cls, context):
        current_slug = context.get('report', {}).get('sub_slug')
        domain = context.get('domain')

        subreport_context = []
        subreports = ADMReport.get_default_subreports(domain, cls.adm_slug)

        if not subreports:
            subreport_context.append({
                'warning_label': 'No ADM Reports Configured',
            })
            return subreport_context

        for report in subreports:
            key = report.get("key", [])
            entry = report.get("value", {})
            report_slug = key[-2]
            if cls.show_subreport_in_navigation(report_slug):
                subreport_context.append({
                    'is_report': True,
                    'is_active': current_slug == report_slug,
                    'url': cls.get_url(domain=domain, subreport=report_slug),
                    'description': entry.get('description', ''),
                    'title': entry.get('name', 'Untitled Report'),
                })
        return subreport_context

    @classmethod
    def show_subreport_in_navigation(cls, subreport_slug):
        return True

