from __future__ import absolute_import, unicode_literals

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.models import FixtureDataType, _id_from_doc
from corehq.apps.fixtures.views import FixtureViewMixIn, fixtures_home
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
        return True if list(FixtureDataType.by_domain(self.domain)) else False

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
        if self.has_tables() and self.request.GET.get("table_id", None):
            return FixtureDataType.get(self.request.GET['table_id'])
        return None

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
        context = super(FixtureEditInterface, self).report_context
        context.update(types=self.data_types)
        return context

    @property
    @memoized
    def data_types(self):
        return list(FixtureDataType.by_domain(self.domain))
