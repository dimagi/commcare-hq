import io
import itertools
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models.query import Prefetch
from django.db.transaction import atomic
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View

from corehq.motech.fhir.const import SUPPORTED_FHIR_RESOURCE_TYPES
from corehq.motech.fhir.models import FHIRResourceType, FHIRResourceProperty
from corehq.project_limits.rate_limiter import RateLimiter, get_dynamic_rate_definition, RateDefinition
from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter

from corehq import toggles
from corehq.apps.case_importer.tracking.filestorage import make_temp_file
from corehq.apps.data_dictionary import util
from corehq.apps.data_dictionary.models import (
    PROPERTY_TYPE_CHOICES,
    CaseProperty,
    CaseType,
)
from corehq.apps.data_dictionary.util import save_case_property
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.settings.views import BaseProjectDataView
from corehq.util.files import file_extention_from_filename
from corehq.util.workbook_reading import open_any_workbook


data_dictionary_rebuild_rate_limiter = RateLimiter(
    feature_key='data_dictionary_rebuilds_per_user',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'data_dictionary_rebuilds_per_user',
        default=RateDefinition(
            per_hour=3,
            per_minute=2,
            per_second=1,
        )
    ).get_rate_limits(),
    scope_length=1,
)

@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def generate_data_dictionary(request, domain):
    if data_dictionary_rebuild_rate_limiter.allow_usage(domain):
        data_dictionary_rebuild_rate_limiter.report_usage(domain)
        try:
            util.generate_data_dictionary(domain)
        except util.OldExportsEnabledException:
            return JsonResponse({
                "failed": "Data Dictionary requires access to new exports"
            }, status=400)

        return JsonResponse({"status": "success"})
    else:
        return JsonResponse({
            "failed": "Rate limit exceeded. Please try again later."
        }, status=429)


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def data_dictionary_json(request, domain, case_type_name=None):
    props = []
    fhir_resource_type_by_case_type = {}
    fhir_resource_prop_by_case_prop = {}
    queryset = CaseType.objects.filter(domain=domain).prefetch_related(
        Prefetch('properties', queryset=CaseProperty.objects.order_by('name'))
    )
    if toggles.FHIR_INTEGRATION.enabled(domain):
        fhir_resource_types = FHIRResourceType.objects.prefetch_related('case_type').filter(domain=domain)
        fhir_resource_type_by_case_type = {
            ft.case_type: ft.name
            for ft in fhir_resource_types
        }
        fhir_resource_prop_by_case_prop = {
            fr.case_property: fr.jsonpath
            for fr in FHIRResourceProperty.objects.prefetch_related('case_property').filter(
                resource_type__in=fhir_resource_types)
        }
    if case_type_name:
        queryset = queryset.filter(name=case_type_name)
    for case_type in queryset:
        p = {
            "name": case_type.name,
            "fhir_resource_type": fhir_resource_type_by_case_type.get(case_type),
            "properties": [],
        }
        for prop in case_type.properties.all():
            p['properties'].append({
                "description": prop.description,
                "fhir_resource_prop_path": fhir_resource_prop_by_case_prop.get(prop),
                "name": prop.name,
                "data_type": prop.data_type,
                "group": prop.group,
                "deprecated": prop.deprecated,
            })
        props.append(p)
    return JsonResponse({'case_types': props})


# atomic decorator is a performance optimization for looped saves
# as per http://stackoverflow.com/questions/3395236/aggregating-saves-in-django#comment38715164_3397586
@atomic
@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def update_case_property(request, domain):
    property_list = json.loads(request.POST.get('properties'))
    fhir_resource_type = request.POST.get('fhir_resource_type')
    fhir_resource_type_obj = None
    case_type = request.POST.get('case_type')
    errors = []
    if fhir_resource_type and case_type:
        case_type_obj = CaseType.objects.get(domain=domain, name=case_type)
        try:
            fhir_resource_type_obj = FHIRResourceType.objects.get(case_type=case_type_obj, domain=domain)
        except FHIRResourceType.DoesNotExist:
            fhir_resource_type_obj = FHIRResourceType(case_type=case_type_obj, domain=domain)
        fhir_resource_type_obj.name = fhir_resource_type
        try:
            fhir_resource_type_obj.save()
        except ValidationError as e:
            errors.append(str(e))

    for property in property_list:
        case_type = property.get('caseType')
        name = property.get('name')
        description = property.get('description')
        fhir_resource_prop_path = property.get('fhir_resource_prop_path')
        data_type = property.get('data_type')
        group = property.get('group')
        deprecated = property.get('deprecated')
        error = save_case_property(name, case_type, domain, data_type, description, group, deprecated,
                                   fhir_resource_prop_path, fhir_resource_type_obj)
        if error:
            errors.append(error)

    if errors:
        return JsonResponse({"status": "failed", "errors": errors}, status=400)
    else:
        return JsonResponse({"status": "success"})


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def update_case_property_description(request, domain):
    case_type = request.POST.get('caseType')
    name = request.POST.get('name')
    description = request.POST.get('description')
    error = save_case_property(name, case_type, domain, description=description)
    if error:
        return JsonResponse({"status": "failed", "errors": error}, status=400)
    else:
        return JsonResponse({"status": "success"})


def _export_data_dictionary(domain):
    queryset = CaseType.objects.filter(domain=domain).prefetch_related(
        Prefetch('properties', queryset=CaseProperty.objects.order_by('name'))
    )
    export_data = {}
    for case_type in queryset:
        export_data[case_type.name or _("No Name")] = [{
            _('Case Property'): prop.name,
            _('Group'): prop.group,
            _('Data Type'): prop.data_type,
            _('Description'): prop.description,
            _('Deprecated'): prop.deprecated
        } for prop in case_type.properties.all()]
    headers = (_('Case Property'), _('Group'), _('Data Type'), _('Description'), _('Deprecated'))
    outfile = io.BytesIO()
    writer = Excel2007ExportWriter()
    header_table = [(tab_name, [headers]) for tab_name in export_data]
    writer.open(header_table=header_table, file=outfile)
    for tab_name, tab in export_data.items():
        tab_rows = []
        for row in tab:
            tab_rows.append([row.get(header, '') for header in headers])
        writer.write([(tab_name, tab_rows)])
    writer.close()
    return outfile


class ExportDataDictionaryView(View):
    urlname = 'export_data_dictionary'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(ExportDataDictionaryView, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, *args, **kwargs):
        outfile = _export_data_dictionary(domain)
        response = HttpResponse(content_type=Format.from_format('xlsx').mimetype)
        response['Content-Disposition'] = 'attachment; filename="data_dictionary.xlsx"'
        response.write(outfile.getvalue())
        return response


class DataDictionaryView(BaseProjectDataView):
    page_title = _("Data Dictionary")
    template_name = "data_dictionary/base.html"
    urlname = 'data_dictionary'

    @method_decorator(login_and_domain_required)
    @use_jquery_ui
    @method_decorator(toggles.DATA_DICTIONARY.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(DataDictionaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        main_context = super(DataDictionaryView, self).main_context
        fhir_integration_enabled = toggles.FHIR_INTEGRATION.enabled(self.domain)
        if fhir_integration_enabled:
            main_context.update({
                'fhir_resource_types': SUPPORTED_FHIR_RESOURCE_TYPES,
            })
        main_context.update({
            'question_types': [{'value': k, 'display': v} for k, v in PROPERTY_TYPE_CHOICES if k],
            'fhir_integration_enabled': fhir_integration_enabled,
        })
        return main_context


class UploadDataDictionaryView(BaseProjectDataView):
    page_title = _("Upload Data Dictionary")
    template_name = "hqwebapp/bulk_upload.html"
    urlname = 'upload_data_dict'

    @method_decorator(login_and_domain_required)
    @use_jquery_ui
    @method_decorator(toggles.DATA_DICTIONARY.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(UploadDataDictionaryView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': DataDictionaryView.page_title,
            'url': reverse(DataDictionaryView.urlname, args=(self.domain,)),
        }]

    @property
    def page_context(self):
        main_context = super(UploadDataDictionaryView, self).main_context
        main_context.update({
            'bulk_upload': {
                "download_url": reverse('export_data_dictionary', args=[self.domain]),
                "adjective": _("data dictionary"),
                "plural_noun": _("data dictionary"),
            },
        })
        main_context.update({
            'bulk_upload_form': get_bulk_upload_form(main_context),
        })
        return main_context

    @method_decorator(atomic)
    def post(self, request, *args, **kwargs):
        bulk_file = self.request.FILES['bulk_upload_file']
        errors = _process_bulk_upload(bulk_file, self.domain)
        if errors:
            messages.error(request, errors)
        else:
            messages.success(request, _('Data dictionary import complete'))
        return self.get(request, *args, **kwargs)


def _process_bulk_upload(bulk_file, domain):
    filename = make_temp_file(bulk_file.read(), file_extention_from_filename(bulk_file.name))
    errors = []
    with open_any_workbook(filename) as workbook:
        for worksheet in workbook.worksheets:
            case_type = worksheet.title
            for row in itertools.islice(worksheet.iter_rows(), 1, None):
                name, group, data_type, description, deprecated = [cell.value for cell in row[:5]]
                if name:
                    error = save_case_property(name, case_type, domain, data_type, description, group, deprecated)
                    if error:
                        errors.append(error)
    return errors
