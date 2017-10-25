from __future__ import absolute_import
from tastypie.fields import ToManyField
from tastypie.resources import ModelResource
from corehq.apps.accounting.models import Feature, FeatureRate, SoftwarePlanVersion, LineItem, PaymentMethod, \
    BillingAccount, BillingContactInfo, Currency, PaymentRecord, SoftwareProductRate, \
    SoftwarePlan, DefaultProductPlan, CreditAdjustment, Subscription, CreditLine, Subscriber, \
    SubscriptionAdjustment, BillingRecord, Invoice
from corehq.apps.api.resources.auth import AdminAuthentication
from tastypie import fields

from corehq.apps.api.resources.meta import CustomResourceMeta
from django_prbac.models import Role
import six


class AccToManyField(ToManyField):

    def dehydrate(self, bundle, for_list=True):
        related_objects = super(AccToManyField, self).dehydrate(bundle, for_list)
        only_ids = []
        if related_objects:
            for ro in related_objects:
                only_ids.append(ro.obj.id)
        return only_ids


class AccountingResourceMeta(CustomResourceMeta):
    authentication = AdminAuthentication()
    list_allowed_methods = ['get']
    detail_allowed_methods = ['get']
    include_resource_uri = False
    filtering = {
        'last_modified': ['gt', 'gte', 'lt', 'lte'],
        'date_updated': ['gt', 'gte', 'lt', 'lte']
    }


class FeatureResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Feature.objects.all().order_by('pk')
        fields = ['id', 'name', 'feature_type', 'last_modified']
        resource_name = 'accounting_features'


class FeatureRateResource(ModelResource):
    feature = fields.IntegerField('feature_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = FeatureRate.objects.all().order_by('pk')
        fields = ['id', 'monthly_fee', 'monthly_limit',
                  'per_excess_fee', 'date_created', 'is_active', 'last_modified']
        resource_name = 'accounting_feature_rates'


class RoleResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Role.objects.all().order_by('pk')
        fields = ['id', 'slug', 'name', 'description', 'parameters', 'last_modified']
        resource_name = 'role'


class AccountingCurrencyResource(ModelResource):

    def build_filters(self, filters=None):
        update = {}
        for key, val in six.iteritems(filters):
            args = key.split('__')
            if args and args[0] == 'last_modified':
                k = 'date_updated__%s' % args[1]
                update.update({k: val})
        filters.update(update)
        return super(AccountingCurrencyResource, self).build_filters(filters)

    class Meta(AccountingResourceMeta):
        queryset = Currency.objects.all().order_by('pk')
        fields = ['id', 'code', 'name', 'symbol', 'rate_to_default', 'date_updated']
        resource_name = 'accounting_currency'


class SoftwarePlanResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = SoftwarePlan.objects.all().order_by('pk')
        fields = ['id', 'name', 'description', 'visibility', 'edition', 'last_modified']
        resource_name = 'software_plan'


class DefaultProductPlanResource(ModelResource):
    plan = fields.IntegerField('plan_id', null=False)

    class Meta(AccountingResourceMeta):
        queryset = DefaultProductPlan.objects.all().order_by('pk')
        fields = ['id', 'edition', 'is_trial', 'last_modified']
        resource_name = 'default_product_plan'


class SoftwareProductRateResource(ModelResource):
    product = fields.IntegerField('product_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = SoftwareProductRate.objects.all().order_by('pk')
        fields = ['id', 'name', 'monthly_fee', 'date_created', 'is_active', 'last_modified']
        resource_name = 'software_product_rate'


class SoftwarePlanVersionResource(ModelResource):
    plan = fields.IntegerField('plan_id', null=True)
    feature_rates = AccToManyField(FeatureRateResource, 'feature_rates', full=True, null=True)
    role = fields.IntegerField('role_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = SoftwarePlanVersion.objects.all().order_by('pk')
        fields = ['id', 'date_created', 'is_active', 'last_modified']
        resource_name = 'software_plan_versions'

    def dehydrate(self, bundle):
        bundle.data['product_rates'] = [bundle.obj.product_rate.id]
        return bundle


class SubscriberResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Subscriber.objects.all().order_by('pk')
        fields = ['id', 'domain', 'organization', 'last_modified']
        resource_name = 'subscriber'


class BillingContactInfoResource(ModelResource):
    account = fields.IntegerField('account_id')
    emails = fields.CharField(readonly=True)

    class Meta(AccountingResourceMeta):
        queryset = BillingContactInfo.objects.all().order_by('pk')
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'company_name', 'first_line',
                  'second_line', 'city', 'state_province_region', 'postal_code', 'country', 'last_modified']
        resource_name = 'billing_contact_info'

    def dehydrate_emails(self, bundle):
        return ','.join(bundle.obj.email_list)


class BillingAccountResource(ModelResource):
    currency = fields.IntegerField('currency_id', null=True)
    billing_contact_info = fields.ToOneField(BillingContactInfoResource,
                                             'billingcontactinfo',
                                             full=True,
                                             null=True)

    class Meta(AccountingResourceMeta):
        queryset = BillingAccount.objects.all().order_by('pk')
        fields = ['id', 'name', 'salesforce_account_id', 'created_by', 'date_created', 'is_auto_invoiceable',
                  'account_type', 'created_by_domain', 'date_confirmed_extra_charges', 'is_active',
                  'dimagi_contact', 'entry_point', 'last_modified', 'last_payment_method', 'pre_or_post_pay']
        resource_name = 'billing_account'


class SubscriptionResource(ModelResource):
    account = fields.IntegerField('account_id', null=True)
    plan_version = fields.IntegerField('plan_version_id', null=True)
    subscriber = fields.IntegerField('subscriber_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = Subscription.objects.all().order_by('pk')
        fields = ['id', 'salesforce_contract_id', 'date_start', 'date_end', 'date_delay_invoicing',
                  'date_created', 'is_active', 'do_not_invoice', 'auto_generate_credits', 'is_trial',
                  'service_type', 'pro_bono_status', 'last_modified', 'funding_source', 'is_hidden_to_ops',
                  'skip_auto_downgrade']
        resource_name = 'subscription'


class InvoiceResource(ModelResource):
    subscription = fields.IntegerField('subscription_id')
    subtotal = fields.DecimalField('subtotal')
    applied_credit = fields.DecimalField('applied_credit')

    class Meta(AccountingResourceMeta):
        queryset = Invoice.api_objects.all().order_by('pk')
        fields = ['id', 'tax_rate', 'balance', 'date_due', 'date_paid', 'date_created',
                  'date_start', 'date_end', 'is_hidden', 'is_hidden_to_ops', 'last_modified']
        resource_name = 'invoice'


class LineItemResource(ModelResource):
    invoice = fields.IntegerField('invoice_id', null=True)
    feature_rate = fields.IntegerField('feature_rate_id', null=True)
    product_rate = fields.IntegerField('product_rate_id', null=True)
    subtotal = fields.DecimalField('subtotal')
    applied_credit = fields.DecimalField('applied_credit')

    class Meta(AccountingResourceMeta):
        queryset = LineItem.objects.all().order_by('pk')
        fields = ['id', 'base_description', 'base_cost', 'unit_description', 'unit_cost', 'quantity',
                  'last_modified']
        resource_name = 'accounting_line_items'
        filtering = {
            'last_modified': ['gt', 'gte', 'lt', 'lte'],
            'date_updated': ['gt', 'gte', 'lt', 'lte'],
            'invoice': ['exact']
        }


class PaymentMethodResource(ModelResource):
    account = fields.IntegerField('account_id', null=True)
    web_user = fields.CharField('web_user', null=True)

    class Meta(AccountingResourceMeta):
        queryset = PaymentMethod.objects.all().order_by('pk')
        fields = ['id', 'method_type', 'customer_id', 'date_created', 'last_modified']
        resource_name = 'accounting_payment_method'


class PaymentRecordResource(ModelResource):
    payment_method = fields.IntegerField('payment_method_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = PaymentRecord.objects.all().order_by('pk')
        fields = ['id', 'date_created', 'transaction_id', 'amount', 'last_modified']
        resource_name = 'payment_record'


class CreditLineResource(ModelResource):
    account = fields.IntegerField('account_id', null=True)
    subscription = fields.IntegerField('subscription_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = CreditLine.objects.all().order_by('pk')
        fields = ['id', 'is_product', 'feature_type', 'date_created', 'balance', 'is_active', 'last_modified']
        resource_name = 'credit_line'


class CreditAdjustmentResource(ModelResource):
    credit_line = fields.IntegerField('credit_line_id', null=True)
    line_item = fields.IntegerField('line_item_id', null=True)
    invoice = fields.IntegerField('invoice_id', null=True)
    payment_record = fields.IntegerField('payment_record_id', null=True)
    related_credit = fields.IntegerField('related_credit_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = CreditAdjustment.objects.all().order_by('pk')
        fields = ['id', 'reason', 'note', 'amount', 'date_created', 'web_user', 'last_modified']
        resource_name = 'credit_adjustment'


class SubscriptionAndAdjustmentResource(ModelResource):

    subscription = fields.IntegerField('subscription_id', null=True)
    related_subscription = fields.IntegerField('related_subscription_id', null=True)
    invoice = fields.IntegerField('invoice_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = SubscriptionAdjustment.objects.all().order_by('pk')
        fields = ['id', 'reason', 'method', 'note', 'web_user', 'invoice', 'date_created', 'new_date_start',
                  'new_date_end', 'new_date_delay_invoicing', 'new_salesforce_contract_id', 'last_modified']
        resource_name = 'subscription_and_adjustment'


class BillingRecordResource(ModelResource):
    invoice = fields.IntegerField('invoice_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = BillingRecord.objects.all().order_by('pk')
        fields = ['id', 'date_created', 'emailed_to', 'pdf_data_id', 'skipped_email', 'last_modified']
        resource_name = 'billing_record'
