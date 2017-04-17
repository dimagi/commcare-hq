from django.db.models import Q
from django.http import JsonResponse
from corehq.apps.motech.connected_accounts import get_openmrs_account
from corehq.apps.motech.openmrs.concepts.models import OpenmrsConcept
from corehq.apps.motech.openmrs.concepts.sync import \
    openmrs_concept_json_with_answers_from_concept, sync_concepts_from_openmrs
from corehq.apps.motech.permissions import require_motech_permissions


@require_motech_permissions
def all_openmrs_concepts(request, domain):
    account = get_openmrs_account(domain)

    concepts = OpenmrsConcept.objects.filter(account=account, openmrsconcept=None)
    return JsonResponse({'concepts': [
        openmrs_concept_json_with_answers_from_concept(concept).to_json()
        for concept in concepts
    ]})


@require_motech_permissions
def concept_search(request, domain):
    search = request.GET.get('q') or ''
    uuid = request.GET.get('uuid')
    account = get_openmrs_account(domain)
    if uuid:
        try:
            concept = OpenmrsConcept.objects.get(uuid=uuid, account=account)
        except OpenmrsConcept.DoesNotExist:
            return JsonResponse({'concepts': []})
        else:
            return JsonResponse({'concepts': [
                openmrs_concept_json_with_answers_from_concept(concept).to_json()
            ]})
    elif len(search) > 2:
        all_openmrs_concepts = OpenmrsConcept.objects.filter(Q(account=account) & ~Q(answers=None))
        openmrs_concepts = all_openmrs_concepts.filter(names__icontains=search)
        first_50 = openmrs_concepts[:50]
        return JsonResponse({'concepts': [
            openmrs_concept_json_with_answers_from_concept(concept).to_json()
            for concept in first_50
        ]})
    else:
        return JsonResponse({'concepts': []})


@require_motech_permissions
def sync_concepts(request, domain):
    sync_concepts_from_openmrs(get_openmrs_account(domain))
    return JsonResponse({'ok': True})
