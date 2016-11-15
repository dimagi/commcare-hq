import json
from django.core import serializers
from django.http import JsonResponse
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.data_dictionary import util
from corehq.apps.data_dictionary.models import CaseProperty


@login_and_domain_required
def generate_data_dictionary(request, domain):
    util.generate_data_dictionary(domain)
    return JsonResponse({"status": "success"})


@login_and_domain_required
def data_dictionary_json(request, domain):
    props = []
    queryset = CaseProperty.objects.filter(domain=domain).only(
        'description', 'case_type', 'property_name', 'type'
    )
    for prop in queryset:
        props.append({
            'description': prop.description,
            'case_type': prop.case_type,
            'property_name': prop.property_name,
            'type': prop.type,
        })
    return JsonResponse({'properties': props})
