from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.fields import ReportSelectField
from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem, _id_from_doc, FieldList, FixtureTypeField, FixtureItemField
from corehq.apps.fixtures.views import data_table, require_can_edit_fixtures
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_noop
from django.utils.decorators import method_decorator
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup


class FixtureInterface(GenericReportView):
    section_name = ugettext_noop("Lookup Tables")
    base_template = 'fixtures/fixtures_base.html'
    asynchronous = False
    dispatcher = FixtureInterfaceDispatcher
    exportable = False
    needs_filters = False


class FixtureSelectField(ReportSelectField):
    slug = "table_id"
    name = ugettext_noop("Select a Table")
    cssId = "select_table"
    cssClasses = "span2"

    @property
    def field_opts(self):
        fdts = list(FixtureDataType.by_domain(self.domain))
        return fdts

    @property
    def default_option(self):
        if not self.field_opts:
            return "NO TABLE"
        return "Default: " + self.field_opts[0].tag

    def update_params(self):
        self.selected = self.request.GET.get(self.slug, '')
        unselected_list = [fo for fo in self.field_opts if fo != self.selected]
        self.options = [{'val': _id_from_doc(f), 'text': f.tag} for f in unselected_list]


class FixtureViewInterface(GenericTabularReport, FixtureInterface):
    name = ugettext_noop("View Tables")
    slug = "view_lookup_tables"

    report_template_path = 'fixtures/view_table.html'

    fields = ['corehq.apps.fixtures.interface.FixtureSelectField']

    @property
    def report_context(self):
        context = super(FixtureViewInterface, self).report_context
        if not context["report_table"].get("rows"):
            self.report_template_path = 'fixtures/no_table.html'
        return context

    @property
    @memoized
    def table(self):
        return data_table(self.request, self.domain)

    @property
    def headers(self):
        return self.table["headers"]

    @property
    def rows(self):
        return self.table["rows"]


class FixtureEditInterface(FixtureInterface):
    name = ugettext_noop("Manage Tables")
    slug = "edit_lookup_tables"

    report_template_path = 'fixtures/manage_tables.html'

    @property
    def report_context(self):
        context = super(FixtureInterface, self).report_context
        context.update(types=self.data_types)
        return context

    @property
    def data_types(self):
        fdts = list(FixtureDataType.by_domain(self.domain))
        return fdts
