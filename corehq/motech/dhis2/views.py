import json

from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_http_methods, require_POST

from memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.dhis2.dbaccessors import (
    get_dataset_maps,
    get_dhis2_connection,
)
from corehq.motech.dhis2.dhis2_config import Dhis2FormConfig, Dhis2EntityConfig
from corehq.motech.dhis2.forms import Dhis2ConfigForm, Dhis2ConnectionForm, Dhis2EntityConfigForm
from corehq.motech.dhis2.models import DataSetMap, DataValueMap
from corehq.motech.dhis2.repeaters import Dhis2Repeater, Dhis2EntityRepeater
from corehq.motech.dhis2.tasks import send_datasets
from corehq.motech.requests import Requests


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

        def update_dataset_map(instance, new_dataset_map):
            new_dataset_map.pop('domain', None)  # Make sure a user cannot change the value of "domain"
            for key, value in new_dataset_map.items():
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
            return JsonResponse({'success': _('DHIS2 DataSet Maps saved')})
        except Exception as err:
            return JsonResponse({'error': str(err)}, status=400)

    @property
    def page_context(self):

        def to_json(dataset_map):
            dataset_map = dataset_map.to_json()
            del(dataset_map['_id'])
            del(dataset_map['_rev'])
            del(dataset_map['doc_type'])
            del(dataset_map['domain'])
            for datavalue_map in dataset_map['datavalue_maps']:
                del(datavalue_map['doc_type'])
            return dataset_map

        dataset_maps = [to_json(d) for d in get_dataset_maps(self.request.domain)]
        return {
            'dataset_maps': dataset_maps,
            'send_data_url': reverse('send_dhis2_data', kwargs={'domain': self.domain}),
            'is_json_ui': int(self.request.GET.get('json', 0)),
        }


@require_POST
@require_permission(Permissions.edit_motech)
def send_dhis2_data(request, domain):
    send_datasets.delay(domain, send_now=True)
    return JsonResponse({'success': _('Data is being sent to DHIS2.')}, status=202)


@login_and_domain_required
@require_http_methods(["GET", "POST"])
def config_dhis2_repeater(request, domain, repeater_id):
    repeater = Dhis2Repeater.get(repeater_id)
    assert repeater.domain == domain, f'"{repeater.domain}" != "{domain}"'

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


@login_and_domain_required
@require_http_methods(["GET", "POST"])
def config_dhis2_entity_repeater(request, domain, repeater_id):
    repeater = Dhis2EntityRepeater.get(repeater_id)
    assert repeater.domain == domain
    if request.method == 'POST':
        errors = []
        case_configs = []
        case_types = set()
        post_data = json.loads(request.POST["case_configs"])
        for case_config in post_data:
            form = Dhis2EntityConfigForm(data={"case_config": json.dumps(case_config)})
            if form.is_valid():
                case_configs.append(form.cleaned_data["case_config"])
                case_types.add(form.cleaned_data["case_config"]["case_type"])
            else:
                # form.errors is a dictionary where values are lists.
                errors.extend([err for errlist in form.errors.values() for err in errlist])
        if len(case_types) < len(case_configs):
            errors.append(_('You cannot have more than one case config for the same case type.'))
        if errors:
            return JsonResponse({'errors': errors}, status=400)
        else:
            repeater.dhis2_entity_config = Dhis2EntityConfig.wrap({
                "case_configs": case_configs
            })
            repeater.save()
            return JsonResponse({'success': _('DHIS2 Tracked Entity configuration saved')})

    else:
        case_configs = [
            case_config.to_json()
            for case_config in repeater.dhis2_entity_config.case_configs
        ]
    return render(request, 'dhis2/dhis2_entity_config.html', {
        'domain': domain,
        'repeater_id': repeater_id,
        'case_configs': case_configs,
    })
