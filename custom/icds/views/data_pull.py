from django.contrib import messages
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _

from custom.icds import icds_toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.locations.permissions import location_safe
from corehq.apps.settings.views import BaseProjectDataView
from custom.icds.const import (
    DATA_PULL_PERMITTED_END_HOUR,
    DATA_PULL_PERMITTED_START_HOUR,
)
from custom.icds.forms import CustomDataPullForm
from custom.icds.utils.data_pull import (
    can_initiate_data_pull,
    data_pull_is_in_progress,
)


@location_safe
@method_decorator([login_and_domain_required,
                   icds_toggles.RUN_CUSTOM_DATA_PULL_REQUESTS.required_decorator()], name='dispatch')
class CustomDataPull(BaseProjectDataView):
    urlname = 'icds_custom_data_pull'
    page_title = "ICDS Custom Data Pull"
    template_name = 'icds/custom_data_pull.html'

    @use_jquery_ui  # for datepicker
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

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
            'data_pull_permitted_start_hour': DATA_PULL_PERMITTED_START_HOUR,
            'data_pull_permitted_end_hour': DATA_PULL_PERMITTED_END_HOUR,
            'data_pull_is_in_progress': data_pull_is_in_progress(),
            'form': self.form
        }

    def post(self, request, *args, **kwargs):
        if not can_initiate_data_pull():
            messages.warning(request, _("Request Ignored."))
        elif not data_pull_is_in_progress() and self.form.is_valid():
            self.form.submit(request.domain, request.user.email)
            messages.success(request, _("Request Initiated. You will receive an email on completion."))
            return redirect(self.urlname, self.domain)
        return self.get(request, *args, **kwargs)
