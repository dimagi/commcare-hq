from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy, ugettext as _
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import ListView, DetailView
from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.dhis2.dbaccessors import get_dhis2_connection, get_dataset_maps
from corehq.motech.dhis2.forms import Dhis2ConnectionForm
from corehq.motech.dhis2.models import DataValueMap, DataSetMap, JsonApiLog
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.motech.dhis2.tasks import send_datasets, refresh_dhis2_name_cache
from memoized import memoized
from dimagi.utils.couch import get_redis_client
from dimagi.utils.web import json_response
from six.moves import range


@login_and_domain_required
@require_http_methods(['POST'])
def dhis2_fetch_names(request, domain):
    refresh_dhis2_name_cache.delay(request.domain)
    return JsonResponse({'status': 'Accepted'}, status=202)


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class Dhis2ConnectionView(BaseProjectSettingsView):
    urlname = 'dhis2_connection_view'
    page_title = ugettext_lazy("DHIS2 Connection Settings")
    template_name = 'dhis2/connection_settings.html'

    def post(self, request, *args, **kwargs):
        form = self.dhis2_connection_form
        if form.is_valid():
            form.save(self.domain)
            get_dhis2_connection.clear(request.domain)
            refresh_dhis2_name_cache.delay(request.domain)
            return HttpResponseRedirect(self.page_url)
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    @property
    @memoized
    def dhis2_connection_form(self):
        dhis2_conn = get_dhis2_connection(self.request.domain)
        initial = dict(dhis2_conn) if dhis2_conn else {}
        if self.request.method == 'POST':
            return Dhis2ConnectionForm(self.request.POST, initial=initial)
        return Dhis2ConnectionForm(initial=initial)

    @property
    def page_context(self):
        return {'dhis2_connection_form': self.dhis2_connection_form}


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class DataSetMapView(BaseProjectSettingsView):
    urlname = 'dataset_map_view'
    page_title = ugettext_lazy("DHIS2 DataSet Maps")
    template_name = 'dhis2/dataset_map.html'

    def post(self, request, *args, **kwargs):

        def update_dataset_map(instance, dict_):
            for key, value in dict_.items():
                if key == 'datavalue_maps':
                    value = [DataValueMap(**v) for v in value]
                instance[key] = value

        try:
            new_dataset_maps = json.loads(request.POST['dataset_maps'])
            current_dataset_maps = get_dataset_maps(request.domain)
            i = -1
            for i, dataset_map in enumerate(current_dataset_maps):
                if i < len(new_dataset_maps):
                    # Update current dataset maps
                    update_dataset_map(dataset_map, new_dataset_maps[i])
                    dataset_map.save()
                else:
                    # Delete removed dataset maps
                    dataset_map.delete()
            if i + 1 < len(new_dataset_maps):
                # Insert new dataset maps
                for j in range(i + 1, len(new_dataset_maps)):
                    dataset_map = DataSetMap(domain=request.domain)
                    update_dataset_map(dataset_map, new_dataset_maps[j])
                    dataset_map.save()
            get_dataset_maps.clear(request.domain)
            return json_response({'success': _('DHIS2 DataSet Maps saved')})
        except Exception as err:
            return json_response({'error': str(err)}, status_code=500)

    @staticmethod
    def get_data_sets(domain):
        cache = get_redis_client()
        key = domain + '_dhis2_id_display_names'
        dhis2_data = cache.get(key)
        if dhis2_data is None:
            refresh_dhis2_name_cache.delay(domain)
            return [{'id': '0', 'name': _('Fetching DHIS2 names. Please refresh page in a minute.')}]
        return [{'id': item['id'], 'name': item['name']} for item in dhis2_data['data_sets'].values()]

    @property
    def page_context(self):
        dataset_maps = [d.to_json() for d in get_dataset_maps(self.request.domain)]
        return {
            'dataset_maps': dataset_maps,
            'send_data_url': reverse('send_dhis2_data', kwargs={'domain': self.domain}),
            'data_sets': self.get_data_sets(self.request.domain),
        }


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class Dhis2LogListView(BaseProjectSettingsView, ListView):
    urlname = 'dhis2_log_list_view'
    page_title = ugettext_lazy("DHIS2 Logs")
    template_name = 'dhis2/logs.html'
    context_object_name = 'logs'
    paginate_by = 100

    def get_queryset(self):
        return JsonApiLog.objects.filter(domain=self.domain).order_by('-timestamp').only(
            'timestamp',
            'request_method',
            'request_url',
            'response_status',
        )

    @property
    def object_list(self):
        return self.get_queryset()


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class Dhis2LogDetailView(BaseProjectSettingsView, DetailView):
    urlname = 'dhis2_log_detail_view'
    page_title = ugettext_lazy("DHIS2 Logs")
    template_name = 'dhis2/log_detail.html'
    context_object_name = 'log'

    def get_queryset(self):
        return JsonApiLog.objects.filter(domain=self.domain)

    @property
    def object(self):
        return self.get_object()

    @property
    @memoized
    def page_url(self):
        pk = self.kwargs['pk']
        return reverse(self.urlname, args=[self.domain, pk])


@require_POST
@require_permission(Permissions.edit_motech)
def send_dhis2_data(request, domain):
    send_datasets.delay(domain, send_now=True)
    return json_response({'success': _('Data is being sent to DHIS2.')}, status_code=202)


def get_data_elements(request, domain, data_set_id):
    cache = get_redis_client()
    key = domain + '_dhis2_id_display_names'
    dhis2_data = cache.get(key)
    if dhis2_data is None:
        # This view is only called from the DataSet Map page. If we get here, DataSetMapView.get_data_sets will
        # already have scheduled a task to fetch the names again
        return json_response({'error': _('DHIS2 names unavailable.')}, status_code=404)
    try:
        return json_response(dhis2_data['data_sets'][data_set_id]['data_elements'].values())
    except KeyError:
        return json_response({'error': 'Unknown dataSetId'}, status_code=400)


def get_cat_opt_combos(request, domain, data_set_id):
    cache = get_redis_client()
    key = domain + '_dhis2_id_display_names'
    dhis2_data = cache.get(key)
    if dhis2_data is None:
        # If we get here, DataSetMapView.get_data_sets will already have scheduled a task to fetch the names again
        return json_response({'error': _('DHIS2 names unavailable.')}, status_code=404)
    try:
        return json_response(dhis2_data['data_sets'][data_set_id]['category_option_combos'].values())
    except KeyError:
        return json_response({'error': 'Unknown dataSetId'}, status_code=400)
