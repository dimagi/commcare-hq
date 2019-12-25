from django.contrib import messages
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.permissions import location_safe
from corehq.apps.settings.views import BaseProjectDataView
from custom.icds.forms import CustomDataPullForm


@location_safe
@method_decorator([login_and_domain_required,
                   toggles.RUN_CUSTOM_DATA_PULL_REQUESTS.required_decorator()], name='dispatch')
class CustomDataPull(BaseProjectDataView):
    urlname = 'icds_custom_data_pull'
    page_title = "ICDS Custom Data Pull"
    template_name = 'icds/custom_data_pull.html'

    @cached_property
    def form(self):
        return CustomDataPullForm(
            self.request,
            self.domain,
            data=self.request.POST if self.request.method == "POST" else None,
        )

    @property
    def page_context(self):
        return {
            'form': self.form
        }

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.form.submit(request.user.email)
            messages.success(request, _("Request Initiated. You will receive an email on completion."))
            return redirect(self.urlname, self.domain)
        else:
            return self.get(request, *args, **kwargs)
