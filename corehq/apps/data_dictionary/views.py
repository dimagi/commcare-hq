import json

import itertools
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models.query import Prefetch
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.db.transaction import atomic

from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.couch import CriticalSection

from corehq import toggles
from corehq.apps.case_importer.tracking.filestorage import make_temp_file
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.data_dictionary import util
from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.style.decorators import use_jquery_ui
from corehq.tabs.tabclasses import ApplicationsTab

from couchexport.writers import Excel2007ExportWriter
from couchexport.models import Format

from StringIO import StringIO

from corehq.util.files import file_extention_from_filename
from corehq.util.workbook_reading import open_any_workbook


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def generate_data_dictionary(request, domain):
    try:
        util.generate_data_dictionary(domain)
    except util.OldExportsEnabledException:
        return JsonResponse({
            "failed": "Data Dictionary requires access to new exports"
        }, status=400)

    return JsonResponse({"status": "success"})


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def data_dictionary_json(request, domain, case_type_name=None):
    props = []
    queryset = CaseType.objects.filter(domain=domain).prefetch_related(
        Prefetch('properties', queryset=CaseProperty.objects.order_by('name'))
    )
    if case_type_name:
        queryset = queryset.filter(name=case_type_name)
    for case_type in queryset:
        p = {
            "name": case_type.name,
            "properties": [],
        }
        for prop in case_type.properties.all():
            p['properties'].append({
                "description": prop.description,
                "name": prop.name,
                "data_type": prop.data_type,
                "group": prop.group
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
    for property in property_list:
        case_type = property.get('caseType')
        name = property.get('name')
        description = property.get('description')
        data_type = property.get('data_type')
        group = property.get('group')
        try:
            prop = CaseProperty.objects.get(
                name=name, case_type__name=case_type, case_type__domain=domain
            )
        except CaseProperty.DoesNotExist:
            key = 'data-dict-property-{domain}-{type}-{name}'.format(
                domain=domain, type=case_type, name=name
            )
            with CriticalSection([key]):
                case_type_obj = CaseType.objects.get(domain=domain, name=case_type)
                prop = CaseProperty.objects.create(case_type=case_type_obj, name=name)
        if data_type:
            prop.data_type = data_type
        if description:
            prop.description = description
        if group:
            prop.group = group
        try:
            prop.full_clean()
        except ValidationError as e:
            return JsonResponse({"status": "failed", "error": unicode(e)}, status=400)
        prop.save()
    return JsonResponse({"status": "success"})


def export_data_dictionary(request, domain):
    queryset = CaseType.objects.filter(domain=domain).prefetch_related(
        Prefetch('properties', queryset=CaseProperty.objects.order_by('name'))
    )
    export_data = {}
    for case_type in queryset:
        export_data[case_type.name] = [{
            'Case Property': prop.name,
            'Group': prop.group,
            'Data Type': prop.data_type,
            'Description': prop.description,
        } for prop in case_type.properties.all()]
    headers = ('Case Property', 'Group', 'Data Type', 'Description')
    outfile = StringIO()
    writer = Excel2007ExportWriter()
    header_table = [(tab_name, [headers]) for tab_name in export_data]
    writer.open(header_table=header_table, file=outfile)
    for tab_name, tab in export_data.items():
        tab_rows = []
        for row in tab:
            tab_rows.append([row.get(header, '') for header in headers])
        writer.write([(tab_name, tab_rows)])
    writer.close()
    response = HttpResponse(content_type=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename="data_dictionary.xlsx"'
    response.write(outfile.getvalue())
    return response


class DataDictionaryView(BaseProjectDataView):
    section_name = _("Data Dictionary")
    template_name = "data_dictionary/base.html"
    urlname = 'data_dictionary'

    @method_decorator(login_and_domain_required)
    @use_jquery_ui
    @toggles.DATA_DICTIONARY.required_decorator()
    def dispatch(self, request, *args, **kwargs):
        return super(DataDictionaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        main_context = super(DataDictionaryView, self).main_context
        main_context.update({
            'active_tab': ApplicationsTab(
                self.request,
                domain=self.domain,
                couch_user=self.request.couch_user,
                project=self.request.project
            ),
        })
        return main_context

    @property
    @memoized
    def section_url(self):
        return reverse(DataDictionaryView.urlname, args=[self.domain])


class UploadDataDictionaryView(BaseProjectDataView):
    section_name = _("Data Dictionary")
    template_name = "data_dictionary/import_data_dict.html"
    urlname = 'upload_data_dict'

    @method_decorator(login_and_domain_required)
    @use_jquery_ui
    @toggles.DATA_DICTIONARY.required_decorator()
    def dispatch(self, request, *args, **kwargs):
        return super(UploadDataDictionaryView, self).dispatch(request, *args, **kwargs)

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
        filename = make_temp_file(bulk_file.read(), file_extention_from_filename(bulk_file.name))
        with open_any_workbook(filename) as workbook:
            for worksheet in workbook.worksheets:
                case_type = worksheet.title
                for row in itertools.islice(worksheet.iter_rows(), 1, None):
                    name, group, data_type, description = [cell.value for cell in row[:4]]
                    if name:
                        try:
                            prop = CaseProperty.objects.get(
                                name=name, case_type__name=case_type, case_type__domain=self.domain
                            )
                        except CaseProperty.DoesNotExist:
                            key = 'data-dict-property-{domain}-{type}-{name}'.format(
                                domain=self.domain, type=case_type, name=name
                            )
                            with CriticalSection([key]):
                                case_type_obj = CaseType.objects.get(domain=self.domain, name=case_type)
                                prop = CaseProperty.objects.create(case_type=case_type_obj, name=name)
                        if data_type:
                            prop.data_type = data_type
                        if description:
                            prop.description = description
                        if group:
                            prop.group = group
                        try:
                            prop.full_clean()
                        except ValidationError as e:
                            messages.error(request, unicode(e))
                            return self.get(request, *args, **kwargs)
                        prop.save()
        messages.success(request, _('Data dictionary import complete'))
        return self.get(request, *args, **kwargs)
