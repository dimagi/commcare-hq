from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView


@method_decorator([
    use_bootstrap5,
    toggles.PROJECT_DB.required_decorator(),
    domain_admin_required,
], name='dispatch')
class QueryProjectDBView(BaseProjectDataView):
    urlname = 'query_project_db'
    page_title = gettext_lazy("Query ProjectDB")
    template_name = 'project_db/query_project_db.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])
