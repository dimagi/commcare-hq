from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.project_db.table_ddl import (
    get_domain_tables,
    get_project_db_engine,
)
from corehq.apps.project_db.user_sql import UnsupportedSQL, translate
from corehq.apps.settings.views import BaseProjectDataView
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action

MAX_ROWS = 100


def run_user_sql(domain, sql):
    """Run user-supplied SQL against ``domain``'s tables, returning columns and rows"""
    query = translate(sql, get_domain_tables(domain))
    with get_project_db_engine().connect() as conn:
        result = conn.execute(query)
        return list(result.keys()), result.fetchmany(MAX_ROWS)


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
    def run_query(self, request, *args, **kwargs):
        context = {'sql': request.POST.get('sql', '')}
        try:
            columns, rows = run_user_sql(self.domain, context['sql'])
        except UnsupportedSQL as error:
            context['error'] = str(error)
        else:
            context.update({'columns': columns, 'rows': rows, 'max_rows': MAX_ROWS})
        return self.render_htmx_partial_response(
            request, 'project_db/partials/query_results.html', context)
