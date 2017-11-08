from __future__ import absolute_import

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from corehq.apps.domain.decorators import require_superuser_or_developer
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.hqcase.tasks import explode_case_task, delete_exploded_case_task
from corehq.apps.hqwebapp.decorators import use_select2
from corehq.apps.users.models import CommCareUser
from corehq.apps.es.case_search import CaseSearchES, CasePropertyAggregation
from soil import DownloadBase


class ExplodeCasesView(BaseProjectSettingsView, TemplateView):
    url_name = "explode_cases"
    template_name = "hqcase/explode_cases.html"
    page_title = "Explode Cases"

    @use_select2
    @method_decorator(require_superuser_or_developer)
    def dispatch(self, *args, **kwargs):
        return super(ExplodeCasesView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ExplodeCasesView, self).get_context_data(**kwargs)
        context.update({
            'domain': self.domain,
            'users': CommCareUser.by_domain(self.domain),
            'previous_explosions': self._get_previous_explosions()
        })
        return context

    def _get_previous_explosions(self):
        results = CaseSearchES().domain(self.domain).aggregation(
            CasePropertyAggregation('explosions', 'cc_explosion_id')
        ).size(0).run()

        return sorted(
            results.aggregations.explosions.counts_by_bucket().items(),
            key=lambda x: -x[1]  # sorted by number of cases
        )

    def post(self, request, domain):
        if 'explosion_id' in request.POST:
            return self.delete_cases(request, domain)
        else:
            return self.explode_cases(request, domain)

    def explode_cases(self, request, domain):
        user_id = request.POST.get('user_id')
        factor = request.POST.get('factor', '2')
        try:
            factor = int(factor)
        except ValueError:
            messages.error(request, 'factor must be an int; was: %s' % factor)
        else:
            download = DownloadBase()
            res = explode_case_task.delay(user_id, self.domain, factor)
            download.set_task(res)

            return redirect('hq_soil_download', self.domain, download.download_id)

    def delete_cases(self, request, domain):
        explosion_id = request.POST.get('explosion_id')
        download = DownloadBase()
        res = delete_exploded_case_task.delay(self.domain, explosion_id)
        download.set_task(res)
        return redirect('hq_soil_download', self.domain, download.download_id)
