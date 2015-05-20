from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.http import HttpResponseRedirect
from corehq.apps.hqwebapp.models import ProjectDataTab
from corehq.apps.fixtures.views import fixtures_home, FixtureViewMixIn
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.models import FixtureDataType, _id_from_doc
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_noop, ugettext as _


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
        context.update({
            "selected_table": self.table.get("table_id", ""),
            'active_tab': ProjectDataTab(
                self.request,
                self.slug,
                domain=self.domain,
                couch_user=self.request.couch_user,
                project=self.request.project
            )
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
        context.update({
            'active_tab': ProjectDataTab(
                self.request,
                self.slug,
                domain=self.domain,
                couch_user=self.request.couch_user,
                project=self.request.project
            )
        })
        return context

    @property
    @memoized
    def data_types(self):
        return list(FixtureDataType.by_domain(self.domain))
