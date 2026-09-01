from django.http import HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.project_db.describe import describe_project_db
from corehq.apps.project_db.table_ddl import get_domain_tables
from corehq.apps.project_db.user_sql import UserSQL, UserSQLValidationError
from corehq.apps.settings.views import BaseProjectDataView
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action

MAX_ROWS = 100


@method_decorator([
    use_bootstrap5,
    toggles.PROJECT_DB.required_decorator(),
    domain_admin_required,
], name='dispatch')
class QueryProjectDBView(HqHtmxActionMixin, BaseProjectDataView):
    urlname = 'query_project_db'
    page_title = gettext_lazy("Query ProjectDB")
    template_name = 'project_db/query_project_db.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {'table_names': sorted(get_domain_tables(self.domain))}

    @hq_hx_action('post')
    def process_query(self, request, *args, **kwargs):
        """Translate the query, running it if it takes no parameters"""
        return self._query_response(request, always_run=False)

    @hq_hx_action('post')
    def run_query_with_parameters(self, request, *args, **kwargs):
        """Run the query with the parameter values given on the page"""
        return self._query_response(request, always_run=True)

    def _query_response(self, request, always_run):
        submitted_params = {
            name.removeprefix('param:'): value
            for name, value in request.POST.items()
            if name.startswith('param:')
        }
        context = {'max_rows': MAX_ROWS}
        user_sql = UserSQL(self.domain, request.POST.get('sql', ''))
        try:
            context['query'] = user_sql.get_info()
            if always_run or not user_sql.parameters:
                context['result'] = user_sql.run(submitted_params, MAX_ROWS)
        except UserSQLValidationError as error:
            context['error'] = error.msg
        else:
            # Re-render parameters with values previously submitted for them
            context['parameters'] = [
                {'name': name, 'value': submitted_params.get(name, '')}
                for name in user_sql.parameters
            ]
        return self.render_htmx_partial_response(
            request, 'project_db/partials/query_results.html', context)

    @hq_hx_action('post')
    def copy_db_context(self, request, *args, **kwargs):
        return HttpResponse(describe_project_db(self.domain))
