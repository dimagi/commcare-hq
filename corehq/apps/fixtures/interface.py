from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop, gettext_lazy

from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.models import LookupTable
from corehq.apps.fixtures.views import FixtureViewMixIn, fixtures_home, table_json
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport


class FixtureInterface(FixtureViewMixIn, GenericReportView):
    base_template = 'fixtures/fixtures_base.html'
    asynchronous = False
    dispatcher = FixtureInterfaceDispatcher
    exportable = False
    needs_filters = False


class FixtureSelectFilter(BaseSingleOptionFilter):
    slug = "table_id"
    label = ""
    placeholder = "place"
    default_text = gettext_lazy("Select a Table")

    @property
    def selected(self):
        # ko won't display default selected-value as it should, display default_text instead
        return ""

    def _fixture_options(self):
        return sorted(
            LookupTable.objects.by_domain(self.domain).values("id", "tag"),
            key=lambda t: t["tag"].lower()
        )

    @property
    @memoized
    def options(self):
        return [(f["id"].hex, f["tag"]) for f in self._fixture_options()]


class FixtureViewInterface(GenericTabularReport, FixtureInterface):
    name = gettext_noop("View Tables")
    slug = "view_lookup_tables"

    report_template_path = 'fixtures/view_table.html'

    fields = ['corehq.apps.fixtures.interface.FixtureSelectFilter']

    @property
    def view_response(self):
        if not self.has_tables():
            messages.info(self.request, _("You don't have any tables defined yet - create tables to view them."))
            return HttpResponseRedirect(fixtures_home(self.domain))
        else:
            return super(FixtureViewInterface, self).view_response

    @property
    def report_context(self):
        assert self.has_tables()
        if not self.request.GET.get("table_id", None):
            return {"table_not_selected": True}
        try:
            context = super(FixtureViewInterface, self).report_context
        except ResourceNotFound:
            return {"table_not_selected": True}

        # Build javascript options for DataTables
        report_table = context['report_table']
        headers = report_table.get('headers')
        data_tables_options = {
            'slug': self.context['report']['slug'],
            'defaultRows': report_table.get('default_rows', 10),
            'startAtRowNum': report_table.get('start_at_row', 0),
            'showAllRowsOption': report_table.get('show_all_rows'),
            'autoWidth': headers.auto_width,
        }
        if headers.render_aoColumns:
            data_tables_options.update({
                'aoColumns': headers.render_aoColumns,
            })
        if headers.custom_sort:
            data_tables_options.update({
                'customSort': headers.custom_sort,
            })

        pagination = context['report_table'].get('pagination', {})
        if pagination.get('is_on'):
            data_tables_options.update({
                'ajaxSource': pagination.get('source'),
                'ajaxParams': pagination.get('params'),
            })

        left_col = context['report_table'].get('left_col', {})
        if left_col.get('is_fixed'):
            data_tables_options.update({
                'fixColumns': True,
                'fixColsNumLeft': left_col['fixed'].get('num'),
                'fixColsWidth': left_col['fixed'].get('width'),
            })

        context.update({
            "selected_table": self.table.get("table_id", ""),
            'data_tables_options': data_tables_options,
        })
        if self.lookup_table:
            context.update({
                "table_description": self.lookup_table.description,
            })
        return context

    @memoized
    def has_tables(self):
        return LookupTable.objects.filter(domain=self.domain).exists()

    @property
    @memoized
    def table(self):
        from corehq.apps.fixtures.views import data_table
        if self.has_tables() and self.request.GET.get("table_id", None):
            return data_table(self.request, self.domain)
        else:
            return {"headers": None, "rows": None}

    @cached_property
    def lookup_table(self):
        try:
            return LookupTable.objects.get(id=self.request.GET['table_id'])
        except LookupTable.DoesNotExist:
            return None

    @property
    def headers(self):
        return self.table["headers"]

    @property
    def rows(self):
        return self.table["rows"]


class FixtureEditInterface(FixtureInterface):
    name = gettext_noop("Manage Tables")
    slug = "edit_lookup_tables"

    report_template_path = 'fixtures/manage_tables.html'

    @property
    def report_context(self):
        context = super(FixtureEditInterface, self).report_context
        is_managed_by_upstream_domain = any(data_type['is_synced'] for data_type in self.data_types)
        context.update(
            types=self.data_types,
            is_managed_by_upstream_domain=is_managed_by_upstream_domain,
            can_edit_linked_data=self.can_edit_linked_data(),
        )
        return context

    @property
    @memoized
    def data_types(self):
        return [table_json(t) for t in LookupTable.objects.by_domain(self.domain)]

    def can_edit_linked_data(self):
        return self.request.couch_user.can_edit_linked_data(self.domain)
