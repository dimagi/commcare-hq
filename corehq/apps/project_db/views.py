import time

from django.http import HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

import sqlglot
from sqlalchemy.dialects import postgresql

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.project_db.describe import describe_project_db
from corehq.apps.project_db.table_ddl import (
    get_domain_tables,
    get_project_db_engine,
)
from corehq.apps.project_db.user_sql import (
    BadParameters,
    UnsupportedSQL,
    clean_parameters,
    get_parameters,
    translate,
)
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
        context = {'sql': request.POST.get('sql', ''),
                   'max_rows': MAX_ROWS}
        try:
            query = translate(context['sql'], get_domain_tables(self.domain))
        except UnsupportedSQL as error:
            context['error'] = error.msg
        else:
            query_params = get_parameters(query)
            context['query'] = compile_query(query)
            context['parameters'] = [{
                'name': parameter,
                'value': submitted_params.get(parameter, ''),
            } for parameter in query_params]
            if always_run or not query_params:
                try:
                    context['result'] = execute_query(query, submitted_params)
                except BadParameters as error:
                    context['error'] = error.msg
        return self.render_htmx_partial_response(
            request, 'project_db/partials/query_results.html', context)

    @hq_hx_action('post')
    def copy_db_context(self, request, *args, **kwargs):
        return HttpResponse(describe_project_db(self.domain))


def execute_query(query, submitted_params):
    params = clean_parameters(query, submitted_params)
    with get_project_db_engine().connect() as conn:
        start = time.perf_counter()
        result = conn.execute(query, params)
        rows = result.fetchmany(MAX_ROWS)
        return {
            'columns': list(result.keys()),
            'rows': rows,
            'duration': time.perf_counter() - start,
        }


def compile_query(query):
    """Render a SQLAlchemy selectable as pretty-printed PostgreSQL and its bound values"""
    compiled = query.compile(dialect=postgresql.dialect(paramstyle='named'))
    unbound = get_parameters(query)
    return {
        'sql': sqlglot.transpile(str(compiled), read='postgres', write='postgres', pretty=True)[0],
        'params': {name: value for name, value in compiled.params.items()
                   if name not in unbound},
    }
