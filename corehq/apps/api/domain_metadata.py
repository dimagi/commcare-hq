import logging

from corehq.apps.api.serializers import XFormInstanceSerializer
from corehq.apps.domain.models import Domain
from corehq.apps.accounting.models import Subscription
from corehq.apps.api.resources import HqBaseResource, CouchResourceMixin
from corehq.apps.api.resources.v0_1 import (
    CustomResourceMeta,
    AdminAuthentication,
)
from corehq.apps.es.domains import DomainES

from tastypie import fields
from tastypie.exceptions import NotFound
from tastypie.resources import Resource
from dimagi.utils.dates import force_to_datetime


def _get_domain(bundle):
    return bundle.obj


class DomainQuerySetAdapter(object):

    def __init__(self, es_query):
        self.es_query = es_query

    def count(self):
        return self.es_query.size(0).run().total

    def __getitem__(self, item):
        if isinstance(item, slice):
            return map(Domain.wrap, self.es_query.start(item.start).size(item.stop - item.start).run().hits)
        raise ValueError('Invalid type of argument. Item should be an instance of slice class.')


class DomainMetadataResource(CouchResourceMixin, HqBaseResource):
    billing_properties = fields.DictField()
    calculated_properties = fields.DictField()
    domain_properties = fields.DictField()

    # using the default resource dispatch function to bypass our authorization for internal use
    def dispatch(self, request_type, request, **kwargs):
        return Resource.dispatch(self, request_type, request, **kwargs)

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
        try:
            es_data = (DomainES()
                       .in_domains([domain.name])
                       .size(1)
                       .run()
                       .hits[0])
            return {
                prop_name: es_data[prop_name]
                for prop_name in es_data if prop_name[:3] == 'cp_'
            }
        except IndexError:
            logging.exception('Problem getting calculated properties for {}'.format(domain.name))
            return {}

    def dehydrate_domain_properties(self, bundle):
        return _get_domain(bundle)._doc

    def obj_get(self, bundle, **kwargs):
        domain = Domain.get_by_name(kwargs.get('domain'))
        if domain is None:
            raise NotFound
        return domain

    def obj_get_list(self, bundle, **kwargs):
        if kwargs.get('domain'):
            return [self.obj_get(bundle, **kwargs)]
        else:
            filters = {}
            if hasattr(bundle.request, 'GET'):
                filters = bundle.request.GET

            params = {}
            if 'last_modified__lte' in filters:
                params['lte'] = force_to_datetime(filters['last_modified__lte'])

            if 'last_modified__gte' in filters:
                params['gte'] = force_to_datetime(filters['last_modified__gte'])

            return DomainQuerySetAdapter(DomainES().last_modified(**params).sort('last_modified'))

    class Meta(CustomResourceMeta):
        authentication = AdminAuthentication()
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        object_class = Domain
        resource_name = 'project_space_metadata'
        serializer = XFormInstanceSerializer(formats=['json'])
