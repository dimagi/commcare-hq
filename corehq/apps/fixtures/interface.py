from couchdbkit import ResourceNotFound

from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
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


class FixtureSelectFilter(BaseSingleOptionFilter):
    slug = "table_id"
    label = ""
    placeholder = "place"
    default_text = "Select a Table"

    @property
    def selected(self):
        # ko won't display default selected-value as it should, display default_text instead
        return ""

    @property
    @memoized
    def fixtures(self):
        fdts = list(FixtureDataType.by_domain(self.domain))
        return fdts

    @property
    @memoized
    def options(self):
        return [(_id_from_doc(f), f.tag) for f in self.fixtures]


class FixtureViewInterface(GenericTabularReport, FixtureInterface):
    name = ugettext_noop("View Tables")
    slug = "view_lookup_tables"

    report_template_path = 'fixtures/view_table.html'

    fields = ['corehq.apps.fixtures.interface.FixtureSelectFilter']

    @property
    def report_context(self):
        if not self.has_tables():
            self.report_template_path = 'fixtures/no_table.html'
            return {"selected_table": self.table.get("table_id", "")}
        if not self.request.GET.get("table_id", None):
            return {"table_not_selected": True}
        try:
            context = super(FixtureViewInterface, self).report_context
        except ResourceNotFound:
            return {"table_not_selected": True}
        context.update({"selected_table": self.table.get("table_id", "")})
        return context

    @memoized
    def has_tables(self):
        return True if list(FixtureDataType.by_domain(self.domain)) else False

    @property
    @memoized
    def table(self):
        if self.has_tables() and self.request.GET.get("table_id", None):
            return data_table(self.request, self.domain)
        else:
            return {"headers": None, "rows": None}

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
