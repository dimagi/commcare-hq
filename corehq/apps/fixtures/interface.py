from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.fields import ReportSelectField
from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem, _id_from_doc, FieldList, FixtureTypeField, FixtureItemField
from corehq.apps.fixtures.views import data_table
from django.utils.translation import ugettext_noop
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup

class FixtureInterface(GenericReportView):
    # overriding properties from GenericReportView
    section_name = ugettext_noop("Lookup Tables")
    base_template = 'fixtures/fixtures_base.html'
    asynchronous = False
    dispatcher = FixtureInterfaceDispatcher
    exportable = False
    needs_filters = False
    # hide_filters = True

class FixtureSelectField(ReportSelectField):
    slug = "table_id"
    name = "Select a Table"
    cssId = "select_table"
    cssClasses = "span2"

    @property
    def field_opts(self):
        fdts = list(FixtureDataType.by_domain(self.domain))
        return fdts

    @property
    def default_option(self):
        return self.field_opts[-1].tag

    def update_params(self):
        self.selected = self.request.GET.get(self.slug, '')
        self.options = [{'val': _id_from_doc(f), 'text': f.tag} for f in [fo for fo in self.field_opts if fo != self.selected]]

class FixtureViewInterface(GenericTabularReport, FixtureInterface):
    name = ugettext_noop("View Table Data")
    slug = "view_lookup_tables"

    report_template_path = 'fixtures/view_table.html'

    fields = ['corehq.apps.fixtures.interface.FixtureSelectField']
    asynchronous = False
    ajax_pagination = False

    @property
    def table(self):
        return data_table(self.request, self.domain)

    @property
    def headers(self):
        return self.table["headers"]

    @property
    def rows(self):
        return self.table["rows"]


class FixtureEditInterface(FixtureInterface):
    name = ugettext_noop("Manage Table Data")
    slug = "edit_lookup_tables"

    report_template_path = 'reports/async/tabular.html'

    asynchronous = False
    ajax_pagination = True