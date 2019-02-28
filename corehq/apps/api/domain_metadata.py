from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from corehq.apps.api.resources.auth import AdminAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.serializers import XFormInstanceSerializer
from corehq.apps.data_analytics.models import MALTRow, GIRRow
from corehq.apps.domain.models import Domain, DomainAuditRecordEntry
from corehq.apps.accounting.models import Subscription
from corehq.apps.api.resources import HqBaseResource, CouchResourceMixin
from corehq.apps.es.domains import DomainES

from tastypie import fields
from tastypie.exceptions import NotFound
from tastypie.resources import Resource, ModelResource

from dimagi.utils.dates import force_to_datetime
from six.moves import map


def _get_domain(bundle):
    return bundle.obj


class DomainQuerySetAdapter(object):

    def __init__(self, es_query):
        self.es_query = es_query

    def count(self):
        return self.es_query.size(0).run().total

    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(map(Domain.wrap, self.es_query.start(item.start).size(item.stop - item.start).run().hits))
        raise ValueError('Invalid type of argument. Item should be an instance of slice class.')


class DomainMetadataResource(CouchResourceMixin, HqBaseResource):
    billing_properties = fields.DictField()
    calculated_properties = fields.DictField()
    domain_properties = fields.DictField()

    # using the default resource dispatch function to bypass our authorization for internal use
    def dispatch(self, request_type, request, **kwargs):
        return Resource.dispatch(self, request_type, request, **kwargs)

    def dehydrate_billing_properties(self, bundle):
        domain_obj = _get_domain(bundle)
        subscription = Subscription.get_active_subscription_by_domain(domain_obj.name)
        return {
            "date_start": (subscription.date_start
                           if subscription is not None else None),
            "date_end": (subscription.date_end
                         if subscription is not None else None),
            "plan_version": (subscription.plan_version
                             if subscription is not None else None),
        }

    def dehydrate_calculated_properties(self, bundle):
        calc_prop_prefix = 'cp_'
        domain_obj = _get_domain(bundle)
        try:
            es_data = (DomainES()
                       .in_domains([domain_obj.name])
                       .size(1)
                       .run()
                       .hits[0])
            base_properties = {
                prop_name: es_data[prop_name]
                for prop_name in es_data
                if prop_name.startswith(calc_prop_prefix)
            }
            try:
                audit_record = DomainAuditRecordEntry.objects.get(domain=domain_obj.name)
            except DomainAuditRecordEntry.DoesNotExist:
                audit_record = None
            extra_properties = {
                field.name: getattr(audit_record, field.name, 0)
                for field in DomainAuditRecordEntry._meta.fields
                if field.name.startswith(calc_prop_prefix)
            }
            base_properties.update(extra_properties)
            return base_properties
        except IndexError:
            logging.exception('Problem getting calculated properties for {}'.format(domain_obj.name))
            return {}

    def dehydrate_domain_properties(self, bundle):
        return _get_domain(bundle)._doc

    def obj_get(self, bundle, **kwargs):
        domain_obj = Domain.get_by_name(kwargs.get('domain'))
        if domain_obj is None:
            raise NotFound
        return domain_obj

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


class MaltResource(ModelResource):

    class Meta(CustomResourceMeta):
        authentication = AdminAuthentication()
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        queryset = MALTRow.objects.all().order_by('pk')
        resource_name = 'malt_tables'
        fields = ['id', 'month', 'user_id', 'username', 'email', 'user_type',
                  'domain_name', 'num_of_forms', 'app_id', 'device_id',
                  'is_app_deleted', 'wam', 'pam', 'use_threshold', 'experienced_threshold']
        include_resource_uri = False
        filtering = {
            'month': ['gt', 'gte', 'lt', 'lte'],
            'domain_name': ['exact']
        }


class GIRResource(ModelResource):

    class Meta(CustomResourceMeta):
        authentication = AdminAuthentication()
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        queryset = GIRRow.objects.all().order_by('pk')
        resource_name = 'gir_tables'
        fields = [
            'id', 'month', 'domain_name', 'country', 'sector', 'subsector', 'bu',
            'self_service', 'test_domain', 'start_date', 'device_id', 'pam',
            'wams_current', 'active_users', 'using_and_performing', 'not_performing',
            'inactive_experienced', 'inactive_not_experienced', 'not_experienced',
            'not_performing_not_experienced', 'active_ever', 'possibly_exp', 'ever_exp',
            'exp_and_active_ever', 'active_in_span', 'eligible_forms', 'performance_threshold',
            'experienced_threshold',

        ]
        include_resource_uri = False
        filtering = {
            'month': ['gt', 'gte', 'lt', 'lte'],
            'domain_name': ['exact']
        }
