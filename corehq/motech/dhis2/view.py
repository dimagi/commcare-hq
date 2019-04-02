from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy, ugettext as _
from django.views.decorators.http import require_POST, require_http_methods
from django.shortcuts import render
import six
from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.dhis2.dhis2_config import Dhis2FormConfig
from corehq.motech.requests import Requests
from corehq.motech.dhis2.dbaccessors import get_dhis2_connection, get_dataset_maps
from corehq.motech.dhis2.forms import Dhis2ConnectionForm, Dhis2ConfigForm
from corehq.motech.dhis2.models import DataValueMap, DataSetMap
from corehq.motech.dhis2.repeaters import Dhis2Repeater
from corehq.motech.dhis2.tasks import send_datasets
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from memoized import memoized
from dimagi.utils.web import json_response
from six.moves import range
from six.moves import map


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

    @property
    def page_context(self):
        dataset_maps = [d.to_json() for d in get_dataset_maps(self.request.domain)]
        return {
            'dataset_maps': dataset_maps,
            'send_data_url': reverse('send_dhis2_data', kwargs={'domain': self.domain}),
        }


@require_POST
@require_permission(Permissions.edit_motech)
def send_dhis2_data(request, domain):
    send_datasets.delay(domain, send_now=True)
    return json_response({'success': _('Data is being sent to DHIS2.')}, status_code=202)


class Dhis2ModelListViewHelper(object):
    def __init__(self, request, domain, repeater_id):
        self.domain = domain
        self.repeater_id = repeater_id

    @property
    @memoized
    def repeater(self):
        repeater = Dhis2Repeater.get(self.repeater_id)
        assert repeater.domain == self.domain
        return repeater

    @property
    @memoized
    def requests(self):
        return Requests(self.domain, self.repeater.url, self.repeater.username, self.repeater.password)


@login_and_domain_required
@require_http_methods(["GET", "POST"])
def dhis2_edit_config(request, domain, repeater_id):
    helper = Dhis2ModelListViewHelper(request, domain, repeater_id)
    repeater = helper.repeater

    if request.method == 'POST':
        form = Dhis2ConfigForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            repeater.dhis2_config.form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
            repeater.save()

    else:
        form_configs = json.dumps([
            form_config.to_json() for form_config in repeater.dhis2_config.form_configs
        ])
        if six.PY2:
            form_configs = form_configs.decode('utf-8')
        form = Dhis2ConfigForm(
            data={
                'form_configs': form_configs,
            }
        )
    return render(request, 'dhis2/edit_config.html', {
        'domain': domain,
        'repeater_id': repeater_id,
        'form': form
    })
