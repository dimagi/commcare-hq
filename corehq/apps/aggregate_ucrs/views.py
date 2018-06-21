from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.userreports.views import BaseUserConfigReportsView


class AggregateUCRView(BaseUserConfigReportsView):
    template_name = 'aggregate_ucrs/view_aggregate_ucr.html'
    urlname = 'aggregate_ucr'

    @method_decorator(toggles.AGGREGATE_UCRS.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(AggregateUCRView, self).dispatch(request, *args, **kwargs)

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
