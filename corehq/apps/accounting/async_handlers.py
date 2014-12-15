import json
from corehq import Domain, toggles
from corehq.apps.accounting.models import Feature, SoftwareProduct, BillingAccount, SoftwarePlanVersion
from corehq.apps.accounting.utils import fmt_feature_rate_dict, fmt_product_rate_dict
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler, AsyncHandlerError
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.users.models import WebUser


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
        'billing_admins',
        'active_accounts',
        'domain',
        'account',
        'plan_version',
        'new_plan_version',
    ]

    @property
    def country_response(self):
        from django_countries.countries import COUNTRIES
        if self.search_string:
            return filter(lambda x: x[1].lower().startswith(self.search_string.lower()), COUNTRIES)
        return COUNTRIES

    @property
    def billing_admins_response(self):
        all_web_users = WebUser.by_domain(domain=self.request.domain)
        admins = filter(lambda x: x.is_domain_admin and x.username != self.request.couch_user.username,
                        all_web_users)
        admins = filter(lambda x: x.username not in self.existing, admins)
        if self.search_string:
            admins = filter(lambda x: (x.username.lower().startswith(self.search_string.lower())
                                       or self.search_string in x.full_name), admins)
        return [(a.username, "%s (%s)" % (a.full_name, a.username)) for a in admins]

    @property
    def active_accounts_response(self):
        accounts = BillingAccount.objects.filter(is_active=True)
        if self.search_string:
            accounts = accounts.filter(name__contains=self.search_string)
        return [(a.name, a.name) for a in accounts]

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
        ).filter(product_rates__product__product_type=product)
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
