import re

from django.http import Http404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from django.views.generic import DetailView, FormView, ListView

from memoized import memoized

from corehq import toggles
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.forms import (
    ConnectionSettingsFormSet,
    ConnectionSettingsFormSetHelper,
)
from corehq.motech.models import ConnectionSettings, RequestLog


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
class MotechLogListView(BaseProjectSettingsView, ListView):
    urlname = 'motech_log_list_view'
    page_title = ugettext_lazy("Remote API Logs")
    template_name = 'motech/logs.html'
    context_object_name = 'logs'
    paginate_by = 100

    def get_queryset(self):
        filter_from_date = self.request.GET.get("filter_from_date")
        filter_to_date = self.request.GET.get("filter_to_date")
        filter_payload = self.request.GET.get("filter_payload")
        filter_url = self.request.GET.get("filter_url")
        filter_status = self.request.GET.get("filter_status")

        queryset = RequestLog.objects.filter(domain=self.domain)
        if filter_from_date:
            queryset = queryset.filter(timestamp__gte=filter_from_date)
        if filter_to_date:
            queryset = queryset.filter(timestamp__lte=filter_to_date)
        if filter_payload:
            queryset = queryset.filter(payload_id=filter_payload)
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
            'payload_id',
            'request_method',
            'request_url',
            'response_status',
        )

    def get_context_data(self, **kwargs):
        context = super(MotechLogListView, self).get_context_data(**kwargs)
        context.update({
            "filter_from_date": self.request.GET.get("filter_from_date", ""),
            "filter_to_date": self.request.GET.get("filter_to_date", ""),
            "filter_payload": self.request.GET.get("filter_payload", ""),
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
    page_title = ugettext_lazy("Remote API Logs")
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


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
class ConnectionSettingsView(BaseProjectSettingsView, FormView):
    urlname = 'connection_settings_view'
    page_title = ugettext_lazy('Connection Settings')
    template_name = 'motech/connection_settings.html'
    form_class = ConnectionSettingsFormSet  # NOTE: form_class is a formset

    def dispatch(self, request, *args, **kwargs):
        if not (
                toggles.DHIS2_INTEGRATION.enabled_for_request(request)
                or toggles.INCREMENTAL_EXPORTS.enabled_for_request(request)
        ):
            raise Http404()
        return super(ConnectionSettingsView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # BaseConnectionSettingsFormSet needs domain param to add to its
        # form_kwargs. ConnectionSettingsForm needs it to set
        # ConnectionSettings.domain when model instance is saved.
        kwargs['domain'] = self.domain
        kwargs['queryset'] = ConnectionSettings.objects.filter(domain=self.domain)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['helper'] = ConnectionSettingsFormSetHelper()
        return context

    def get_success_url(self):
        # On save, stay on the same page
        return reverse(self.urlname, kwargs={'domain': self.domain})

    def form_valid(self, form):
        self.object = form.save()  # Saves the forms in the formset
        return super().form_valid(form)
