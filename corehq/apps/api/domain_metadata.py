from corehq import Domain
from corehq.apps.accounting.models import Subscription
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.v0_1 import (
    CustomResourceMeta,
    SuperuserAuthentication,
)
from corehq.apps.es.domains import DomainES

from tastypie import fields
from tastypie.exceptions import NotFound


def _get_domain(bundle):
    return bundle.obj


class DomainMetadataResource(HqBaseResource):
    billing_properties = fields.DictField()
    calculated_properties = fields.DictField()
    domain_properties = fields.DictField()

    def dehydrate_billing_properties(self, bundle):
        domain = _get_domain(bundle)
        plan_version, subscription = (
            Subscription.get_subscribed_plan_by_domain(domain)
        )
        return {
            "date_start": (subscription.date_start
                           if subscription is not None else None),
            "date_end": (subscription.date_end
                         if subscription is not None else None),
            "plan_version": plan_version,
        }

    def dehydrate_calculated_properties(self, bundle):
        domain = _get_domain(bundle)
        es_data = (DomainES()
                   .in_domains([domain.name])
                   .run()
                   .raw_hits[0]['_source'])
        return {
            raw_hit: es_data[raw_hit]
            for raw_hit in es_data if raw_hit[:3] == 'cp_'
        }

    def dehydrate_domain_properties(self, bundle):
        domain = _get_domain(bundle)
        return {term: domain[term] for term in domain}

    def obj_get(self, bundle, **kwargs):
        domain = Domain.get_by_name(kwargs.get('domain'))
        if domain is None:
            raise NotFound
        return domain

    def obj_get_list(self, bundle, **kwargs):
        return [self.obj_get(bundle, **kwargs)]

    class Meta(CustomResourceMeta):
        authentication = SuperuserAuthentication()
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        object_class = Domain
        resource_name = 'project_space_metadata'
