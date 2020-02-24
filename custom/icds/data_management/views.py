from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.locations.permissions import location_safe
from corehq.apps.settings.views import BaseProjectDataView
from custom.icds.data_management.forms import DataManagementForm
from custom.icds.data_management.models import DataManagementRequest
from custom.icds.data_management.serializers import (
    DataManagementRequestSerializer,
)


@location_safe
@method_decorator([login_and_domain_required,
                   toggles.RUN_DATA_MANAGEMENT_TASKS.required_decorator()], name='dispatch')
class DataManagementView(BaseProjectDataView):
    urlname = 'data_management'
    page_title = "Data Management"
    template_name = 'data_management/data_management.html'

    @use_jquery_ui  # for datepicker
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def form(self):
        return DataManagementForm(
            self.request,
            self.domain,
            data=self.request.POST if self.request.method == "POST" else None,
        )

    @property
    def page_context(self):
        return {'form': self.form}

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.form.submit(request.domain, request.user.username)
            messages.success(request, _("Request Initiated."))
            return redirect(self.urlname, self.domain)
        return self.get(request, *args, **kwargs)


@toggles.RUN_DATA_MANAGEMENT_TASKS.required_decorator()
@require_GET
def paginate_data_management_requests(request, domain):
    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))

    paginator = Paginator(DataManagementRequest.objects.filter(domain=domain).order_by('-created_at'), limit)
    result = DataManagementRequestSerializer(list(paginator.page(page)), many=True).data

    return JsonResponse({
        'requests': result,
        'total': paginator.count,
        'page': page,
    })
