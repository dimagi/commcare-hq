import logging

from tastypie import fields
from tastypie.exceptions import NotFound
from tastypie.resources import ModelResource, Resource

from dimagi.utils.dates import force_to_datetime

from corehq.apps.accounting.models import Subscription
from corehq.apps.api.resources import CouchResourceMixin, HqBaseResource
from corehq.apps.api.resources.meta import AdminResourceMeta
from corehq.apps.api.serializers import XFormInstanceSerializer
from corehq.apps.data_analytics.models import DomainMetrics, GIRRow, MALTRow
from corehq.apps.domain.models import Domain, DomainAuditRecordEntry
from corehq.apps.es.domains import DomainES


def _get_domain(bundle):
    return bundle.obj


class DomainQuerySetAdapter(object):

    def __init__(self, es_query):
        self.es_query = es_query

    def count(self):
        return self.es_query.count()

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
            base_properties = self._get_base_properties_from_domain_metrics(domain_obj.name)
            properties = self._add_extra_calculated_properties(base_properties, domain_obj.name, calc_prop_prefix)
        except (DomainMetrics.DoesNotExist):
            logging.exception('Problem getting calculated properties for {}'.format(domain_obj.name))
            return {}
        return properties

    @staticmethod
    def _get_base_properties_from_domain_metrics(domain):
        domain_metrics = DomainMetrics.objects.get(domain=domain)
        return domain_metrics.to_calculated_properties()

    @staticmethod
    def _add_extra_calculated_properties(properties, domain, calc_prop_prefix):
        try:
            audit_record = DomainAuditRecordEntry.objects.get(domain=domain)
        except DomainAuditRecordEntry.DoesNotExist:
            audit_record = None
        extra_properties = {
            field.name: getattr(audit_record, field.name, 0)
            for field in DomainAuditRecordEntry._meta.fields
            if field.name.startswith(calc_prop_prefix)
        }
        properties.update(extra_properties)
        return properties

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

    class Meta(AdminResourceMeta):
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        object_class = Domain
        resource_name = 'project_space_metadata'
        serializer = XFormInstanceSerializer(formats=['json'])


class MaltResource(ModelResource):

    class Meta(AdminResourceMeta):
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

    class Meta(AdminResourceMeta):
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
