from __future__ import absolute_import, unicode_literals

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy

from corehq import toggles
from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
from corehq.apps.aggregate_ucrs.tasks import populate_aggregate_table_data_task
from corehq.apps.domain.decorators import login_and_domain_required, login_or_basic
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.userreports.views import BaseUserConfigReportsView, swallow_programming_errors, \
    export_sql_adapter_view
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions


@method_decorator(toggles.AGGREGATE_UCRS.required_decorator(), name='dispatch')
class BaseAggregateUCRView(BaseUserConfigReportsView):

    @property
    def table_id(self):
        return self.kwargs.get('table_id')

    @property
    def table_definition(self):
        return get_object_or_404(
            AggregateTableDefinition, domain=self.domain, table_id=self.table_id
        )

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.table_id))

    @property
    def page_context(self):
        return {
            'aggregate_table': self.table_definition,
        }


class AggregateUCRView(BaseAggregateUCRView):
    template_name = 'aggregate_ucrs/view_aggregate_ucr.html'
    urlname = 'aggregate_ucr'
    page_title = ugettext_lazy("View Aggregate UCR")


class PreviewAggregateUCRView(BaseAggregateUCRView):
    urlname = 'preview_aggregate_ucr'
    template_name = 'aggregate_ucrs/preview_aggregate_ucr.html'
    page_title = ugettext_lazy("Preview Aggregate UCR")

    @method_decorator(swallow_programming_errors)
    def dispatch(self, request, *args, **kwargs):
        return super(PreviewAggregateUCRView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        context = super(PreviewAggregateUCRView, self).page_context
        adapter = get_indicator_adapter(self.table_definition)
        q = adapter.get_query_object()
        context.update({
            'columns': q.column_descriptions,
            'data': [list(row) for row in q[:20]],
            'total_rows': q.count(),
        })
        return context


@login_or_basic
@require_permission(Permissions.view_reports)
@swallow_programming_errors
def export_aggregate_ucr(request, domain, table_id):
    table_definition = get_object_or_404(
        AggregateTableDefinition, domain=domain, table_id=table_id
    )
    aggregate_table_adapter = get_indicator_adapter(table_definition, load_source='export_aggregate_ucr')
    url = reverse('export_aggregate_ucr', args=[domain, table_definition.table_id])
    return export_sql_adapter_view(request, domain, aggregate_table_adapter, url)


@login_and_domain_required
@toggles.AGGREGATE_UCRS.required_decorator()
def rebuild_aggregate_ucr(request, domain, table_id):
    table_definition = get_object_or_404(
        AggregateTableDefinition, domain=domain, table_id=table_id
    )
    aggregate_table_adapter = get_indicator_adapter(table_definition)
    aggregate_table_adapter.rebuild_table(
        initiated_by=request.user.username,
        source='rebuild_aggregate_ucr'
    )
    populate_aggregate_table_data_task.delay(table_definition.id)
    messages.success(request, 'Table rebuild successfully started.')
    return HttpResponseRedirect(reverse(AggregateUCRView.urlname, args=[domain, table_id]))
