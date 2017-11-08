from __future__ import absolute_import

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from corehq.apps.domain.decorators import require_superuser_or_developer
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.hqcase.tasks import explode_case_task
from corehq.apps.users.models import CommCareUser
from soil import DownloadBase


class ExplodeCasesView(BaseProjectSettingsView, TemplateView):
    url_name = "explode_cases"
    template_name = "hqcase/explode_cases.html"
    page_title = "Explode Cases"

    @method_decorator(require_superuser_or_developer)
    def dispatch(self, *args, **kwargs):
        return super(ExplodeCasesView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ExplodeCasesView, self).get_context_data(**kwargs)
        context.update({
            'domain': self.domain,
            'users': CommCareUser.by_domain(self.domain)
        })
        return context

    def post(self, request, domain):
        user_id = request.POST['user_id']
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
