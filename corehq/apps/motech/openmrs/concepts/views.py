import json
from django.db.models import Q
from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import render
from corehq.apps.motech.connceted_accounts import get_openmrs_requests_object, \
    get_openmrs_account
from corehq.apps.motech.openmrs.concepts.models import OpenmrsConcept
from corehq.apps.motech.openmrs.concepts.sync import openmrs_concept_json_from_api_json, \
    openmrs_concept_json_with_answers_from_concept
from corehq.apps.motech.openmrs.restclient.listapi import OpenmrsListApi
from corehq.apps.motech.permissions import require_motech_permissions


@require_motech_permissions
def all_openmrs_concepts(request, domain):
    requests = get_openmrs_requests_object(domain)
    restclient = OpenmrsListApi(requests, 'concept')

    lines = (json.dumps(openmrs_concept_json_from_api_json(concept).to_json()) + '\n'
             for concept in restclient.get_all())
    return StreamingHttpResponse(lines, content_type='text/json')


@require_motech_permissions
def concept_search(request, domain):
    search = request.GET.get('q') or ''
    uuid = request.GET.get('uuid')
    account = get_openmrs_account(domain)
    if uuid:
        try:
            concept = OpenmrsConcept.objects.get(uuid=uuid, account=account)
        except OpenmrsConcept.DoesNotExist:
            return HttpResponse(json.dumps([]), content_type='text/json')
        else:
            return HttpResponse(
                json.dumps([
                    openmrs_concept_json_with_answers_from_concept(concept).to_json()
                ]), content_type='text/json')
    elif len(search) > 2:
        all_openmrs_concepts = OpenmrsConcept.objects.filter(Q(account=account) & ~Q(answers=None))
        openmrs_concepts = all_openmrs_concepts.filter(names__icontains=search)
        first_50 = openmrs_concepts[:50]
        return HttpResponse(
            json.dumps([
                openmrs_concept_json_with_answers_from_concept(concept).to_json()
                for concept in first_50
            ], content_type='text/json')
        )
    else:
        return HttpResponse(json.dumps([]), content_type='text/json')


@require_motech_permissions
def concept_search_page(request, domain):
    return render(request, 'openmrs/concepts/concept_search.html', {
        'domain': domain,
    })
