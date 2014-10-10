from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.generic import View

from corehq import Domain
from corehq.apps.domain.decorators import login_or_digest_ex
from corehq.apps.es.domains import DomainES

from dimagi.utils.web import json_response


def _get_metadata(domain):
    return {
        "calculated_properties": _get_calculated_properties(domain),
        "domain_properties": _get_domain_properties(domain),
    }


def _get_calculated_properties(domain):
    es_data = (DomainES()
               .in_domains([domain.name])
               .run()
               .raw_hits[0]['_source'])
    return {
        raw_hit: es_data[raw_hit]
        for raw_hit in es_data if raw_hit[:3] == 'cp_'
    }


def _get_domain_properties(domain):
    return {term: domain[term] for term in domain}


class DomainMetadataAPI(View):
    @method_decorator(login_or_digest_ex())
    def get(self, request, *args, **kwargs):
        domain_name = args[0]
        try:
            domain = Domain.get_by_name(domain_name)
        except ValueError:
            domain = None
        if not domain:
            raise Http404
        return json_response(_get_metadata(domain))
