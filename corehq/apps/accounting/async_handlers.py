import json
from django.db.models import Q
from corehq.apps.accounting.models import Feature, SoftwareProduct, BillingAccount, SoftwarePlanVersion, \
    Subscription, Subscriber, BillingContactInfo, SoftwarePlan
from corehq.apps.accounting.utils import fmt_feature_rate_dict, fmt_product_rate_dict
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler, AsyncHandlerError
from corehq.apps.hqwebapp.encoders import LazyEncoder


class BaseRateAsyncHandler(BaseAsyncHandler):
    """
    Subclass this for interacting with RatesManager.
    """
    allowed_actions = [
        'apply',
        'create',
    ]

    @property
    def name(self):
        return self.data.get('name')

    @property
    def rate_type(self):
        return self.data.get('rate_type')

    @property
    def rate_id(self):
        return self.data.get('rate_id')

    @property
    def create_response(self):
        raise NotImplementedError("create_response is required")

    @property
    def apply_response(self):
        raise NotImplementedError("apply_response is required")


class FeatureRateAsyncHandler(BaseRateAsyncHandler):
    slug = 'features_handler'

    @property
    def create_response(self):
        if Feature.objects.filter(name=self.name).count() > 0:
            raise AsyncHandlerError("Feature '%s' already exists, and likely already "
                                    "in this Software Plan Version." % self.name)
        new_feature, _ = Feature.objects.get_or_create(
            name=self.name,
            feature_type=self.rate_type,
        )
        return fmt_feature_rate_dict(new_feature)

    @property
    def apply_response(self):
        try:
            feature = Feature.objects.get(id=self.rate_id)
            return fmt_feature_rate_dict(feature)
        except Feature.DoesNotExist:
            raise AsyncHandlerError("could not find an existing feature")


class SoftwareProductRateAsyncHandler(BaseRateAsyncHandler):
    slug = 'products_handler'

    @property
    def create_response(self):
        if SoftwareProduct.objects.filter(name=self.name).count() > 0:
            raise AsyncHandlerError("Product '%s' already exists, and likely already "
                                    "in this Software Plan Version." % self.name)
        new_product, _ = SoftwareProduct.objects.get_or_create(
            name=self.name,
            product_type=self.rate_type
        )
        return fmt_product_rate_dict(new_product)

    @property
    def apply_response(self):
        try:
            product = SoftwareProduct.objects.get(id=self.rate_id)
            return fmt_product_rate_dict(product)
        except SoftwareProduct.DoesNotExist:
            raise AsyncHandlerError("could not find an existing product")


class BaseSelect2AsyncHandler(BaseAsyncHandler):
    @property
    def search_string(self):
        return self.data.get('searchString')

    @property
    def existing(self):
        return self.data.getlist('existing[]')

    def _fmt_success(self, response):
        success = json.dumps({
            'results': [{
                'id': r[0],
                'text': r[1],
            } for r in response]
        }, cls=LazyEncoder)
        return success


class Select2RateAsyncHandler(BaseSelect2AsyncHandler):
    """
    Handles the async responses for the select2 widget in the Features & Rates portion
    of the SoftwarePlanVersion form.
    """
    slug = 'select2_rate'
    allowed_actions = [
        'feature_id',
        'product_id',
    ]

    @property
    def feature_id_response(self):
        features = Feature.objects
        if self.existing:
            features = features.exclude(name__in=self.existing)
        if self.search_string:
            features = features.filter(name__startswith=self.search_string)
        return [(f.id, f.name, f.feature_type) for f in features.all()]

    @property
    def product_id_response(self):
        products = SoftwareProduct.objects
        if self.existing:
            products = products.exclude(name__in=self.existing)
        if self.search_string:
            products = products.filter(name__startswith=self.search_string)
        return [(p.id, p.name, p.product_type) for p in products.all()]

    def _fmt_success(self, response):
        return json.dumps({
            'results': [
            {
                'id': r[0],
                'name': r[1],
                'rate_type': r[2],
                'text': '%s (%s)' % (r[1], r[2]),
                'isExisting': True,
            } for r in response]
        })


class Select2BillingInfoHandler(BaseSelect2AsyncHandler):
    slug = 'select2_billing'
    allowed_actions = [
        'country',
        'active_accounts',
        'domain',
        'account',
        'plan_version',
        'new_plan_version',
    ]

    @property
    def country_response(self):
        from django_countries.data import COUNTRIES
        countries = sorted(COUNTRIES.items(), key=lambda x: x[1].encode('utf-8'))
        if self.search_string:
            return filter(lambda x: x[1].lower().startswith(self.search_string.lower()), countries)
        return countries

    @property
    def active_accounts_response(self):
        accounts = BillingAccount.objects.filter(is_active=True)
        if self.search_string:
            accounts = accounts.filter(name__contains=self.search_string)
        return [(a.id, a.name) for a in accounts]

    @property
    def domain_response(self):
        domain_names = [domain['key'] for domain in Domain.get_all(include_docs=False)]
        if self.search_string:
            domain_names = filter(lambda x: x.lower().startswith(self.search_string.lower()), domain_names)
        return [(name, name) for name in domain_names]

    @property
    def account_response(self):
        accounts = BillingAccount.objects
        if self.search_string:
            accounts = accounts.filter(name__contains=self.search_string)
        return [(a.id, a.name) for a in accounts.order_by('name')]

    @property
    def plan_version_response(self):
        edition = self.data.get('additionalData[edition]')
        product = self.data.get('additionalData[product]')
        plan_versions = SoftwarePlanVersion.objects.filter(
            plan__edition=edition
        ).filter(product_rate__product__product_type=product)
        if self.search_string:
            plan_versions = plan_versions.filter(
                plan__name__contains=self.search_string)
        return [(p.id, p.__str__()) for p in plan_versions.order_by('plan__name')]

    @property
    def new_plan_version_response(self):
        current_version = int(self.data.get('additionalData[current_version]'))
        plan_versions = filter(lambda x: x[0] != current_version,
                               self.plan_version_response)
        return plan_versions


class Select2InvoiceTriggerHandler(BaseSelect2AsyncHandler):
    slug = 'select2_billing'
    allowed_actions = [
        'domain',
    ]

    @property
    def domain_response(self):
        domain_names = [domain['key'] for domain in Domain.get_all(include_docs=False)]
        if self.search_string:
            domain_names = filter(lambda x: x.lower().startswith(self.search_string.lower()), domain_names)
        return [(d, d) for d in domain_names]


class BaseSingleOptionFilterAsyncHandler(BaseAsyncHandler):

    @property
    def query(self):
        raise NotImplementedError("must return a queryset")

    @property
    def search_string(self):
        return self.data.get('q', None)

    @property
    def page(self):
        return int(self.data.get('page', 1))

    @property
    def paginated_data(self):
        start = (self.page - 1) * self.limit
        end = self.page * self.limit
        return self.query.all()[start:end]

    @property
    def limit(self):
        return self.data.get('limit', 10)

    @property
    def total(self):
        return self.query.count()

    @staticmethod
    def _fmt_select2_data(data_id, data_text):
        return {
            'id': data_id,
            'text': data_text,
        }

    def _fmt_success(self, data):
        return json.dumps({
            'success': True,
            'limit': self.limit,
            'page': self.page,
            'total': self.total,
            'items': data,
        })


class SubscriberFilterAsyncHandler(BaseSingleOptionFilterAsyncHandler):
    slug = 'subscriber_filter'
    allowed_actions = [
        'subscriber',
    ]

    @property
    def query(self):
        query = Subscriber.objects.exclude(domain=None).order_by('domain')
        if self.search_string:
            query = query.filter(domain__istartswith=self.search_string)
        return query

    @property
    def subscriber_response(self):
        return [self._fmt_select2_data(s.domain, s.domain)
                for s in self.paginated_data]


class SubscriptionFilterAsyncHandler(BaseSingleOptionFilterAsyncHandler):
    slug = 'subscription_filter'
    allowed_actions = [
        'contract_id',
    ]

    @property
    def query(self):
        query = Subscription.objects
        if self.action == 'contract_id':
            query = query.exclude(
                salesforce_contract_id=None
            ).exclude(salesforce_contract_id='').order_by('salesforce_contract_id')
            if self.search_string:
                query = query.filter(
                    salesforce_contract_id__istartswith=self.search_string
                )
        return query

    @property
    def contract_id_response(self):
        return [self._fmt_select2_data(
                s.salesforce_contract_id, s.salesforce_contract_id)
                for s in self.paginated_data]


class AccountFilterAsyncHandler(BaseSingleOptionFilterAsyncHandler):
    slug = 'account_filter'
    allowed_actions = [
        'account_name',
        'account_id',
        'dimagi_contact',
    ]

    @property
    def query(self):
        query = BillingAccount.objects.order_by('name')

        if self.action == 'account_name' and self.search_string:
            query = query.filter(name__icontains=self.search_string)

        if self.action == 'account_id':
            query = query.exclude(
                salesforce_account_id=None
            ).exclude(
                salesforce_account_id=''
            ).order_by('salesforce_account_id')
            if self.search_string:
                query = query.filter(
                    salesforce_account_id__istartswith=self.search_string)

        if self.action == 'dimagi_contact':
            query = query.exclude(
                dimagi_contact=None
            ).exclude(
                dimagi_contact=''
            ).order_by('dimagi_contact')
            if self.search_string:
                query = query.filter(
                    dimagi_contact__icontains=self.search_string)

        return query

    @property
    def account_name_response(self):
        return [self._fmt_select2_data(a.name, a.name)
                for a in self.paginated_data]

    @property
    def account_id_response(self):
        return [self._fmt_select2_data(a.salesforce_account_id,
                                       a.salesforce_account_id)
                for a in self.paginated_data]

    @property
    def dimagi_contact_response(self):
        return [self._fmt_select2_data(a.dimagi_contact, a.dimagi_contact)
                for a in self.paginated_data]


class BillingContactInfoAsyncHandler(BaseSingleOptionFilterAsyncHandler):
    slug = 'billing_contact_filter'
    allowed_actions = [
        'contact_name'
    ]

    @property
    def query(self):
        query = BillingContactInfo.objects.exclude(
            first_name='', last_name='').order_by('first_name', 'last_name')
        if self.search_string:
            query = query.filter(
                Q(first_name__istartswith=self.search_string) |
                Q(last_name__istartswith=self.search_string)
            )
        return query

    @property
    def contact_name_response(self):
        return [self._fmt_select2_data(c.full_name, c.full_name)
                for c in self.paginated_data]


class SoftwarePlanAsyncHandler(BaseSingleOptionFilterAsyncHandler):
    slug = 'software_plan_filter'
    allowed_actions = [
        'name',
    ]

    @property
    def query(self):
        query = SoftwarePlan.objects.order_by('name')
        if self.search_string:
            query = query.filter(name__icontains=self.search_string)
        return query

    @property
    def name_response(self):
        return [self._fmt_select2_data(p.name, p.name)
                for p in self.paginated_data]


class DomainFilterAsyncHandler(BaseSingleOptionFilterAsyncHandler):
    slug = 'domain_filter'
    allowed_actions = [
        'domain_name',
    ]

    @property
    def query(self):
        db = Domain.get_db()
        startkey = self.search_string
        endkey = "{}Z".format(self.search_string) if startkey else ''
        query = db.view(
            'domain/domains',
            reduce=False,
            startkey=startkey,
            endkey=endkey,
            limit=20,
        )
        return query

    @property
    def domain_name_response(self):
        return [self._fmt_select2_data(p['key'], p['key']) for p in self.paginated_data]
