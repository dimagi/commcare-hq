import re

from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from django.views.generic import DetailView, ListView

from memoized import memoized

from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.models import RequestLog


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
class MotechLogListView(BaseProjectSettingsView, ListView):
    urlname = 'motech_log_list_view'
    page_title = ugettext_lazy("MOTECH Logs")
    template_name = 'motech/logs.html'
    context_object_name = 'logs'
    paginate_by = 100

    def get_queryset(self):
        filter_from_date = self.request.GET.get("filter_from_date")
        filter_to_date = self.request.GET.get("filter_to_date")
        filter_url = self.request.GET.get("filter_url")
        filter_status = self.request.GET.get("filter_status")

        queryset = RequestLog.objects.filter(domain=self.domain)
        if filter_from_date:
            queryset = queryset.filter(timestamp__gte=filter_from_date)
        if filter_to_date:
            queryset = queryset.filter(timestamp__lte=filter_to_date)
        if filter_url:
            queryset = queryset.filter(request_url__istartswith=filter_url)
        if filter_status:
            if re.match(r'^\d{3}$', filter_status):
                queryset = queryset.filter(response_status=filter_status)
            elif re.match(r'^\dxx$', filter_status.lower()):
                # Filtering response status code by "2xx", "4xx", etc. will
                # return all responses in that range
                status_min = int(filter_status[0]) * 100
                status_max = status_min + 99
                queryset = (queryset.filter(response_status__gte=status_min)
                            .filter(response_status__lt=status_max))
            elif filter_status.lower() == "none":
                queryset = queryset.filter(response_status=None)

        return queryset.order_by('-timestamp').only(
            'timestamp',
            'request_method',
            'request_url',
            'response_status',
        )

    def get_context_data(self, **kwargs):
        context = super(MotechLogListView, self).get_context_data(**kwargs)
        context.update({
            "filter_from_date": self.request.GET.get("filter_from_date", ""),
            "filter_to_date": self.request.GET.get("filter_to_date", ""),
            "filter_url": self.request.GET.get("filter_url", ""),
            "filter_status": self.request.GET.get("filter_status", ""),
        })
        return context

    @property
    def object_list(self):
        return self.get_queryset()


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
class MotechLogDetailView(BaseProjectSettingsView, DetailView):
    urlname = 'motech_log_detail_view'
    page_title = ugettext_lazy("MOTECH Logs")
    template_name = 'motech/log_detail.html'
    context_object_name = 'log'

    def get_queryset(self):
        return RequestLog.objects.filter(domain=self.domain)

    @property
    def object(self):
        return self.get_object()

    @property
    @memoized
    def page_url(self):
        pk = self.kwargs['pk']
        return reverse(self.urlname, args=[self.domain, pk])
