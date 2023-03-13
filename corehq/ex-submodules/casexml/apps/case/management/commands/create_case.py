import uuid

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseFactory, CaseStructure

from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.cases import case_adapter
from corehq.pillows.case import transform_case_for_elasticsearch as es_case_hq
from corehq.pillows.case_search import domain_needs_search_index
from corehq.pillows.case_search import \
    transform_case_for_elasticsearch as es_case_search


class Command(BaseCommand):
    help = "Create a case and populate the ES indexes."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('case_name')
        parser.add_argument('owner_id')
        parser.add_argument('properties', nargs="+",
                            help="Case properties formatted as 'name=value'")

    def handle(self, domain, case_type, case_name, owner_id, **kwargs):
        props = kwargs.get('properties', [])
        properties = dict(
            p.split('=') for p in props
        )
        case_structure = CaseStructure(
            case_id=str(uuid.uuid4()),
            attrs={
                "create": True,
                "case_type": case_type,
                "case_name": case_name,
                "owner_id": owner_id,
                "update": properties,
            },
        )
        [case] = CaseFactory(domain).create_or_update_cases([case_structure], user_id=owner_id)
        case_json = case.to_json()

        case_adapter.index(
            es_case_hq(case_json),
            refresh=True
        )
        if domain_needs_search_index(domain):
            case_search_adapter.index(
                es_case_search(case_json),
                refresh=True
            )
        print(f"Created case with ID: {case.case_id}")
