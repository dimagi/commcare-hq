import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.forms import model_to_dict
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic.edit import BaseCreateView, BaseUpdateView

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.motech.repeaters.forms import GenericRepeaterForm
from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView
from corehq.util.json import CommCareJSONEncoder

from .const import SEND_FREQUENCY_CHOICES
from .dhis2_config import Dhis2EntityConfig, Dhis2FormConfig
from .forms import (
    DataSetMapForm,
    DataValueMapCreateForm,
    DataValueMapUpdateForm,
    Dhis2ConfigForm,
    Dhis2EntityConfigForm,
)
from .models import SQLDataSetMap, SQLDataValueMap
from .repeaters import Dhis2EntityRepeater, Dhis2Repeater
from .tasks import send_dataset


@method_decorator(require_permission(HqPermissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class DataSetMapListView(BaseProjectSettingsView, CRUDPaginatedViewMixin):
    urlname = 'dataset_map_list_view'
    page_title = gettext_lazy("DHIS2 DataSet Maps")
    template_name = 'dhis2/dataset_map_list.html'

    limit_text = _('DataSet Maps per page')
    empty_notification = _('There are no DataSet Maps')
    loading_message = _('Loading DataSet Maps')

    @property
    def total(self):
        return self.base_query.count()

    @property
    def base_query(self):
        return SQLDataSetMap.objects.filter(domain=self.domain)

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        start, end = self.skip, self.skip + self.limit
        for dataset_map in self.base_query.all()[start:end]:
            yield {
                "itemData": self._get_item_data(dataset_map),
                "template": "dataset-map-template",
            }

    @property
    def column_names(self):
        return [
            _('Description'),
            _('Connection Settings'),
            _('Frequency'),
            _('UCR'),

            _('Action')
        ]

    def refresh_item(self, item_id):
        pass

    def _get_item_data(self, dataset_map):
        frequency_names = dict(SEND_FREQUENCY_CHOICES)
        return {
            'id': dataset_map.id,
            'description': dataset_map.description,
            'connectionSettings': str(dataset_map.connection_settings),
            'frequency': frequency_names[dataset_map.frequency],
            'ucr': dataset_map.ucr.title if dataset_map.ucr else None,

            'editUrl': reverse(
                DataSetMapUpdateView.urlname,
                kwargs={'domain': self.domain, 'pk': dataset_map.id}
            ),
            'jsonEditUrl': reverse(
                'dataset_map_json_edit_view',
                kwargs={'domain': self.domain, 'pk': dataset_map.id}
            ),
        }

    def get_deleted_item_data(self, item_id):
        dataset_map = SQLDataSetMap.objects.get(domain=self.domain, pk=item_id)
        dataset_map.delete()
        return {
            'itemData': self._get_item_data(dataset_map),
            'template': 'dataset-map-deleted-template',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


@method_decorator(require_permission(HqPermissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class DataSetMapJsonCreateView(BaseProjectSettingsView):
    urlname = 'dataset_map_json_create_view'
    page_title = _('DataSet Map')
    template_name = 'dhis2/dataset_map_json.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dataset_map'] = '{}'
        return context

    def post(self, request, domain, **kwargs):
        dsm_dict = json.loads(request.POST['dataset_map'])
        _save_dsm_dict(domain, dsm_dict)
        return JsonResponse({'success': _('DataSet map updated successfully.')})


@method_decorator(require_permission(HqPermissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class DataSetMapJsonEditView(BaseProjectSettingsView):
    urlname = 'dataset_map_json_edit_view'
    page_title = _('DataSet Map')
    template_name = 'dhis2/dataset_map_json.html'

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs=self.kwargs)

    def get_context_data(self, **kwargs):
        dataset_map_id = kwargs['pk']
        dataset_map = get_object_or_404(
            SQLDataSetMap,
            domain=self.domain,
            id=dataset_map_id,
        )
        dsm_dict = _dsm_to_dict(dataset_map)
        dsm_json = json.dumps(dsm_dict, cls=CommCareJSONEncoder)

        context = super().get_context_data(**kwargs)
        context['dataset_map'] = dsm_json
        return context

    def post(self, request, domain, **kwargs):
        dsm_dict = json.loads(request.POST['dataset_map'])
        _save_dsm_dict(domain, dsm_dict)
        return JsonResponse({'success': _('DataSet map updated successfully.')})


def _dsm_to_dict(dataset_map):
    dataset_map_dict = model_to_dict(dataset_map)
    dataset_map_dict['connection_settings_id'] = dataset_map_dict.pop(
        'connection_settings', None
    )
    dataset_map_dict['datavalue_maps'] = [
        model_to_dict(dvm, exclude=('id', 'dataset_map'))
        for dvm in dataset_map.datavalue_maps.all()
    ]
    return dataset_map_dict


def _save_dsm_dict(domain, dsm_dict):
    dsm_dict_domain = dsm_dict.pop('domain', None)
    if dsm_dict_domain and dsm_dict_domain != domain:
        raise ValidationError(_('Invalid value for "domain"'))

    dvm_dicts = dsm_dict.pop('datavalue_maps', [])
    pk = dsm_dict.pop('id', None)
    dataset_map, __ = SQLDataSetMap.objects.update_or_create(
        domain=domain,
        pk=pk,
        defaults=dsm_dict,
    )
    dataset_map.datavalue_maps.all().delete()
    for dvm_dict in dvm_dicts:
        dataset_map.datavalue_maps.create(**dvm_dict)


class DataSetMapCreateView(BaseCreateView, BaseProjectSettingsView):
    urlname = 'dataset_map_create_view'
    page_title = _('DataSet Map')
    template_name = 'dhis2/dataset_map_create.html'
    model = SQLDataSetMap
    form_class = DataSetMapForm

    @method_decorator(require_permission(HqPermissions.edit_motech))
    @method_decorator(toggles.DHIS2_INTEGRATION.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(domain=self.domain)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        return kwargs

    def get_success_url(self):
        return reverse(
            DataSetMapListView.urlname,
            kwargs={'domain': self.domain},
        )


class DataSetMapUpdateView(BaseUpdateView, BaseProjectSettingsView,
                           CRUDPaginatedViewMixin):
    urlname = 'dataset_map_update_view'
    page_title = _('DataSet Map')
    template_name = 'dhis2/dataset_map_update.html'
    model = SQLDataSetMap
    form_class = DataSetMapForm

    limit_text = _('DataValue Maps per page')
    empty_notification = _('This DataSet Map has no DataValue Maps')
    loading_message = _('Loading DataValue Maps')

    @method_decorator(require_permission(HqPermissions.edit_motech))
    @method_decorator(toggles.DHIS2_INTEGRATION.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(domain=self.domain)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        return kwargs

    def get_success_url(self):
        return reverse(
            DataSetMapListView.urlname,
            kwargs={'domain': self.domain},
        )

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['pk']])

    def post(self, request, *args, **kwargs):
        post_response = super().post(request, *args, **kwargs)
        try:
            return self.paginate_crud_response
        except Http404:
            # POST was a DataSetMapForm, not a CRUD action
            # See CRUDPaginatedViewMixin.allowed_actions
            # **NOTE:** This means that DataSetMapForm cannot have a
            #           field named "action"
            pass
        return post_response

    @property
    def total(self):
        return self.base_query.count()

    @property
    def base_query(self):
        return self.object.datavalue_maps

    @property
    def page_context(self):
        return {
            'dataset_map_id': self.kwargs['pk'],
            **self.pagination_context,
        }

    @property
    def paginated_list(self):
        start, end = self.skip, self.skip + self.limit
        for datavalue_map in self.base_query.all()[start:end]:
            yield {
                "itemData": self._get_item_data(datavalue_map),
                "template": "datavalue-map-template",
            }

    def refresh_item(self, item_id):
        pass

    def get_create_item_data(self, create_form):
        datavalue_map = create_form.save()
        return {
            'itemData': self._get_item_data(datavalue_map),
            'template': 'new-datavalue-map-template',
        }

    def get_updated_item_data(self, update_form):
        datavalue_map = update_form.save()
        return {
            "itemData": self._get_item_data(datavalue_map),
            "template": "datavalue-map-template",
        }

    def get_deleted_item_data(self, item_id):
        datavalue_map = SQLDataValueMap.objects.get(pk=item_id,
                                                    dataset_map=self.object)
        datavalue_map.delete()
        return {
            'itemData': self._get_item_data(datavalue_map),
            'template': 'deleted-datavalue-map-template',
        }

    @property
    def column_names(self):
        return [
            _('Column'),
            _('DataElementID'),
            _('CategoryOptionComboID'),
            _('Comment'),

            _('Action'),
        ]

    def _get_item_data(self, datavalue_map):
        return {
            'id': datavalue_map.id,
            'column': datavalue_map.column,
            'dataElementId': datavalue_map.data_element_id,
            'categoryOptionComboId': datavalue_map.category_option_combo_id,
            'comment': datavalue_map.comment,

            'updateForm': self.get_update_form_response(
                self.get_update_form(datavalue_map)
            ),
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return DataValueMapCreateForm(self.object, self.request.POST)
        return DataValueMapCreateForm(self.object)

    def get_update_form(self, instance=None):
        if instance is None:
            instance = SQLDataValueMap.objects.get(
                id=self.request.POST.get("id"),
                dataset_map=self.object,
            )
        if self.request.method == 'POST' and self.action == 'update':
            return DataValueMapUpdateForm(self.object, self.request.POST,
                                          instance=instance)
        return DataValueMapUpdateForm(self.object, instance=instance)


@require_POST
@require_permission(HqPermissions.edit_motech)
def send_dataset_now(request, domain, pk):
    dataset_map = SQLDataSetMap.objects.get(domain=domain, pk=pk)
    send_date = datetime.utcnow().date()
    result = send_dataset(dataset_map, send_date)
    return JsonResponse(result, status=result['status_code'] or 500)


@login_and_domain_required
@require_http_methods(["GET", "POST"])
def config_dhis2_repeater(request, domain, repeater_id):
    repeater = Dhis2Repeater.objects.get(id=repeater_id)
    assert repeater.domain == domain, f'"{repeater.domain}" != "{domain}"'

    if request.method == 'POST':
        form = Dhis2ConfigForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            # wrapping here to ensure schema validation and filling in defaults
            cleaned_form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
            # saving back dicts to sql tables
            repeater.dhis2_config['form_configs'] = [config.to_json() for config in cleaned_form_configs]
            repeater.save()
            return JsonResponse({'success': _('DHIS2 Anonymous Events configuration saved')})
        else:
            errors = [err for errlist in form.errors.values() for err in errlist]
            return JsonResponse({'errors': errors}, status=400)
    else:
        form_configs = json.dumps(repeater.dhis2_config['form_configs'])
    return render(request, 'dhis2/dhis2_events_config.html', {
        'domain': domain,
        'repeater_id': repeater_id,
        'form_configs': form_configs
    })


@login_and_domain_required
@require_http_methods(["GET", "POST"])
def config_dhis2_entity_repeater(request, domain, repeater_id):
    repeater = Dhis2EntityRepeater.objects.get(id=repeater_id)
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
            }).to_json()
            repeater.save()
            return JsonResponse({'success': _('DHIS2 Tracked Entity configuration saved')})

    else:
        case_configs = repeater.dhis2_entity_config.get('case_configs', [])
    return render(request, 'dhis2/dhis2_entity_config.html', {
        'domain': domain,
        'repeater_id': repeater_id,
        'case_configs': case_configs,
    })


class AddDhis2RepeaterView(AddRepeaterView):
    urlname = 'new_dhis2_repeater$'
    repeater_form_class = GenericRepeaterForm
    page_title = gettext_lazy("Forward Forms to DHIS2 as Anonymous Events")
    page_name = gettext_lazy("Forward Forms to DHIS2 as Anonymous Events")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])


class EditDhis2RepeaterView(EditRepeaterView, AddDhis2RepeaterView):
    urlname = 'edit_dhis2_repeater'
    page_title = gettext_lazy("Edit DHIS2 Anonymous Event Repeater")


class AddDhis2EntityRepeaterView(AddDhis2RepeaterView):
    urlname = 'new_dhis2_entity_repeater$'
    repeater_form_class = GenericRepeaterForm
    page_title = gettext_lazy("Forward Cases to DHIS2 as Tracked Entities")
    page_name = gettext_lazy("Forward Cases to DHIS2 as Tracked Entities")


class EditDhis2EntityRepeaterView(EditRepeaterView, AddDhis2EntityRepeaterView):
    urlname = 'edit_dhis2_entity_repeater'
    page_title = gettext_lazy("Edit DHIS2 Tracked Entity Repeater")
