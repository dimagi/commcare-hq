import re
from datetime import datetime, timedelta

from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from django.views.generic.edit import ModelFormMixin, ProcessFormView

from django_prbac.utils import has_privilege
from memoized import memoized
from requests import RequestException

from corehq import privileges, toggles
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.const import PASSWORD_PLACEHOLDER
from corehq.motech.forms import ConnectionSettingsForm, UnrecognizedHost
from corehq.motech.models import ConnectionSettings, RequestLog
from no_exceptions.exceptions import Http400

from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt


class Http409(Http400):
    status = 409
    meaning = 'CONFLICT'
    message = "Resource is in use."


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
class MotechLogListView(BaseProjectSettingsView, ListView):
    urlname = 'motech_log_list_view'
    page_title = _("Remote API Logs")
    template_name = 'motech/logs.html'
    context_object_name = 'logs'
    paginate_by = 100

    def get_queryset(self):
        filter_from_date = self.request.GET.get("filter_from_date",
                                                _a_week_ago())
        filter_to_date = self.request.GET.get("filter_to_date")
        filter_payload = self.request.GET.get("filter_payload")
        filter_url = self.request.GET.get("filter_url")
        filter_status = self.request.GET.get("filter_status")

        queryset = (RequestLog.objects
                    .filter(domain=self.domain)
                    .filter(timestamp__gte=filter_from_date))
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
            "filter_from_date": self.request.GET.get("filter_from_date",
                                                     _a_week_ago()),
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
    page_title = _("Remote API Logs")
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


class ConnectionSettingsListView(BaseProjectSettingsView, CRUDPaginatedViewMixin):
    urlname = 'connection_settings_list_view'
    page_title = _('Connection Settings')
    template_name = 'motech/connection_settings.html'

    @method_decorator(require_permission(Permissions.edit_motech))
    def dispatch(self, request, *args, **kwargs):
        if (
            toggles.INCREMENTAL_EXPORTS.enabled_for_request(request)
            or has_privilege(request, privileges.DATA_FORWARDING)
        ):
            return super().dispatch(request, *args, **kwargs)
        raise Http404()

    @property
    def total(self):
        return self.base_query.count()

    @property
    def base_query(self):
        return ConnectionSettings.objects.filter(domain=self.domain)

    @property
    def column_names(self):
        return [
            _("Name"),
            _("URL"),
            _("Notify Addresses"),
            _("Used By"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        start, end = self.skip, self.skip + self.limit
        for connection_settings in self.base_query.all()[start:end]:
            yield {
                "itemData": self._get_item_data(connection_settings),
                "template": "connection-settings-template",
            }

    def _get_item_data(self, connection_settings):
        data = {
            'id': connection_settings.id,
            'name': connection_settings.name,
            'url': connection_settings.url,
            'notifyAddresses': ', '.join(connection_settings.notify_addresses),
            'usedBy': ', '.join(connection_settings.used_by),
        }

        if connection_settings.id is not None:
            data['editUrl'] = reverse(
                ConnectionSettingsDetailView.urlname,
                kwargs={'domain': self.domain, 'pk': connection_settings.id}
            )

        return data

    def get_deleted_item_data(self, item_id):
        connection_settings = ConnectionSettings.objects.get(
            pk=item_id,
            domain=self.domain,
        )
        if connection_settings.used_by:
            raise Http409

        connection_settings.delete()
        return {
            'itemData': self._get_item_data(connection_settings),
            'template': 'connection-settings-deleted-template',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


class ConnectionSettingsDetailView(BaseProjectSettingsView, ModelFormMixin, ProcessFormView):
    urlname = 'connection_settings_detail_view'
    page_title = _('Connection Settings')
    template_name = 'motech/connection_settings_detail.html'
    model = ConnectionSettings
    form_class = ConnectionSettingsForm

    @method_decorator(require_permission(Permissions.edit_motech))
    def dispatch(self, request, *args, **kwargs):
        if (
            toggles.INCREMENTAL_EXPORTS.enabled_for_request(request)
            or has_privilege(request, privileges.DATA_FORWARDING)
        ):
            return super().dispatch(request, *args, **kwargs)
        raise Http404()

    def get_queryset(self):
        return super().get_queryset().filter(domain=self.domain)

    def get(self, request, *args, **kwargs):
        # Allow us to update if 'pk' is given in the URL, otherwise create
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        return kwargs

    def get_success_url(self):
        return reverse(
            ConnectionSettingsListView.urlname,
            kwargs={'domain': self.domain},
        )

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


@require_POST
@require_permission(Permissions.edit_motech)
def test_connection_settings(request, domain):
    if not (
        toggles.INCREMENTAL_EXPORTS.enabled_for_request(request)
        or has_privilege(request, privileges.DATA_FORWARDING)
    ):
        raise Http404

    if request.POST.get('plaintext_password') == PASSWORD_PLACEHOLDER:
        # The user is editing an existing instance, and the form is
        # showing the password placeholder. (We don't tell the user what
        # the API password is.)
        return JsonResponse({
            "success": False,
            "response": _("Please enter API password again."),
        })
    form = ConnectionSettingsForm(domain=domain, data=request.POST)
    if form.is_valid():
        if isinstance(form.cleaned_data['url'], UnrecognizedHost):
            return JsonResponse({"success": False, "response": "Unknown URL"})

        conn = form.save(commit=False)
        requests = conn.get_requests()
        try:
            # Send a GET request to the base URL. That should be enough
            # to test the URL and authentication.
            response = requests.get(endpoint=None)
            if 200 <= response.status_code < 300:
                return JsonResponse({
                    "success": True,
                    "status": response.status_code,
                    "response": response.text,
                })
            else:
                return JsonResponse({
                    "success": False,
                    "status": response.status_code,
                    "response": response.text,
                })
        except RequestException as err:
            return JsonResponse({"success": False, "response": str(err)})
        except PossibleSSRFAttempt:
            return JsonResponse({"success": False, "response": "Invalid URL"})
    else:
        if set(form.errors.keys()) == {'url'}:
            return JsonResponse({
                "success": False,
                "response": form.errors['url'],
            })
        else:
            return JsonResponse({
                "success": False,
                "response": "Try saving the connection first"
            })


def _a_week_ago() -> str:
    last_week = datetime.today() - timedelta(days=7)
    return last_week.strftime('%Y-%m-%d')
