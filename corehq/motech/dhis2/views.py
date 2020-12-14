import json

from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_http_methods, require_POST

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.dhis2.dbaccessors import get_dataset_maps
from corehq.motech.dhis2.dhis2_config import Dhis2EntityConfig, Dhis2FormConfig
from corehq.motech.dhis2.forms import (
    DatasetMapForm,
    Dhis2ConfigForm,
    Dhis2EntityConfigForm,
)
from corehq.motech.dhis2.models import DataSetMap, DataValueMap
from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater, Dhis2Repeater
from corehq.motech.dhis2.tasks import send_datasets
from corehq.motech.models import ConnectionSettings


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
class DataSetMapListView(BaseProjectSettingsView, CRUDPaginatedViewMixin):
    urlname = 'dataset_map_list_view'
    page_title = ugettext_lazy("DHIS2 DataSet Maps")
    template_name = 'dhis2/dataset_map_list.html'  # TODO: delete dhis2/dataset_map.html

    limit_text = _('DataSet maps per page')
    empty_notification = _('You have no DataSet maps')
    loading_message = _('Loading DataSet maps')

    @property
    def total(self):
        dataset_maps = get_dataset_maps(self.domain)
        return len(dataset_maps)

    @property
    def column_names(self):
        return [
            _("Description"),
            _("Frequency"),
            mark_safe("&nbsp;"),  # Column where "Delete" button will appear
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        for dataset_map in get_dataset_maps(self.domain):
            yield {
                "itemData": self._get_item_data(dataset_map),
                "template": "dataset-map-template",
            }

    def _get_item_data(self, dataset_map):
        return {
            'id': dataset_map._id,
            'description': dataset_map.description,
            'frequency': dataset_map.frequency,

            'editUrl': reverse(
                DataSetMapDetailView.urlname,
                kwargs={'domain': self.domain, 'id': dataset_map._id}
            ),
        }

    def get_deleted_item_data(self, item_id):
        dataset_map = DataSetMap.get(item_id)
        assert dataset_map.domain == self.domain, 'Bad domain'
        dataset_map.delete()
        return {
            'itemData': self._get_item_data(dataset_map),
            'template': 'dataset-map-deleted-template',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
@method_decorator(toggles.DHIS2_INTEGRATION.required_decorator(), name='dispatch')
# class DataSetMapDetailView(BaseProjectSettingsView, ModelFormMixin, ProcessFormView):
class DataSetMapDetailView(BaseProjectSettingsView, CRUDPaginatedViewMixin):
    urlname = 'dataset_map_detail_view'
    page_title = _('DataSet Map')
    template_name = 'dhis2/dataset_map_detail.html'
    model = DataSetMap  # NOTE: This is a Couch model
    form_class = DatasetMapForm
    pk_url_kwarg = 'id'

    def get_object(self, *args, **kwargs):
        doc_id = self.kwargs[self.pk_url_kwarg]
        doc = DataSetMap.get_db().open_doc(doc_id)
        assert doc['domain'] == self.domain, \
            f'Document {doc_id} does not belong to domain {self.domain}'
        assert doc['doc_type'] == 'DataSetMap', \
            f'Document {doc_id} is not a DataSetMap'
        return DataSetMap.wrap(doc)

    def get(self, request, *args, **kwargs):
        # Allow us to update if instance ID is given in the URL
        # otherwise create
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # TODO: breakpoint here?
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        return kwargs

    def get_success_url(self):
        return reverse(
            DataSetMapListView.urlname,
            kwargs={'domain': self.domain},
        )

    def form_valid(self, form):
        # TODO: breakpoint here?
        # self.object = form.save()
        form.save()  # TODO: Do we need a model for this?!
        return super().form_valid(form)

    # def post(self, request, *args, **kwargs):
    #
    #     def update_dataset_map(instance, new_dataset_map):
    #         new_dataset_map.pop('domain', None)  # Make sure a user cannot change the value of "domain"
    #         for key, value in new_dataset_map.items():
    #             if key == 'datavalue_maps':
    #                 value = [DataValueMap(**v) for v in value]
    #             instance[key] = value
    #
    #     try:
    #         new_dataset_maps = json.loads(request.POST['dataset_maps'])
    #         current_dataset_maps = get_dataset_maps(request.domain)
    #         i = -1
    #         for i, dataset_map in enumerate(current_dataset_maps):
    #             if i < len(new_dataset_maps):
    #                 # Update current dataset maps
    #                 update_dataset_map(dataset_map, new_dataset_maps[i])
    #                 dataset_map.save()
    #             else:
    #                 # Delete removed dataset maps
    #                 dataset_map.delete()
    #         if i + 1 < len(new_dataset_maps):
    #             # Insert new dataset maps
    #             for j in range(i + 1, len(new_dataset_maps)):
    #                 dataset_map = DataSetMap(domain=request.domain)
    #                 update_dataset_map(dataset_map, new_dataset_maps[j])
    #                 dataset_map.save()
    #         get_dataset_maps.clear(request.domain)
    #         return JsonResponse({'success': _('DHIS2 DataSet Maps saved')})
    #     except Exception as err:
    #         return JsonResponse({'error': str(err)}, status=500)

    # @property
    # def page_context(self):
    #
    #     def to_json(dataset_map):
    #         dataset_map = dataset_map.to_json()
    #         del(dataset_map['_id'])
    #         del(dataset_map['_rev'])
    #         del(dataset_map['doc_type'])
    #         del(dataset_map['domain'])
    #         for datavalue_map in dataset_map['datavalue_maps']:
    #             del(datavalue_map['doc_type'])
    #         return dataset_map
    #
    #     dataset_maps = [to_json(d) for d in get_dataset_maps(self.request.domain)]
    #     return {
    #         'dataset_maps': dataset_maps,
    #         'connection_settings': ConnectionSettings.objects.filter(domain=self.domain).all(),
    #         'ucrs': get_report_configs_for_domain(self.domain),
    #         'send_data_url': reverse('send_dhis2_data', kwargs={'domain': self.domain}),
    #         'is_json_ui': int(self.request.GET.get('json', 0)),
    #     }


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
