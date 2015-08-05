from tastypie.fields import ToManyField
from tastypie.resources import ModelResource
from corehq.apps.accounting.models import Feature, FeatureRate, SoftwarePlanVersion, LineItem, PaymentMethod, \
    BillingAccount, BillingContactInfo, Currency, PaymentRecord, SoftwareProductRate, \
    SoftwareProduct, SoftwarePlan, DefaultProductPlan, CreditAdjustment, Subscription, CreditLine, Subscriber, \
    SubscriptionAdjustment, BillingRecord, Invoice
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, AdminAuthentication
from tastypie import fields
from django_prbac.models import Role


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
        queryset = Feature.objects.all()
        fields = ['id', 'name', 'feature_type', 'last_modified']
        resource_name = 'accounting_features'


class FutureRateResource(ModelResource):
    feature = fields.IntegerField('feature_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = FeatureRate.objects.all()
        fields = ['id', 'monthly_fee', 'monthly_limit',
                  'per_excess_fee', 'date_created', 'is_active', 'last_modified']
        resource_name = 'accounting_feature_rates'


class RoleResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Role.objects.all()
        fields = ['id', 'slug', 'name', 'description', 'parameters', 'last_modified']
        resource_name = 'role'


class AccountingCurrencyResource(ModelResource):

    def build_filters(self, filters=None):
        update = {}
        for key, val in filters.iteritems():
            args = key.split('__')
            if args and args[0] == 'last_modified':
                k = 'date_updated__%s' % args[1]
                update.update({k: val})
        filters.update(update)
        return super(AccountingCurrencyResource, self).build_filters(filters)

    class Meta(AccountingResourceMeta):
        queryset = Currency.objects.all()
        fields = ['id', 'code', 'name', 'symbol', 'rate_to_default', 'date_updated']
        resource_name = 'accounting_currency'


class SoftwareProductResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = SoftwareProduct.objects.all()
        fields = ['id', 'name', 'product_type', 'last_modified']
        resource_name = 'software_product'


class SoftwarePlanResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = SoftwarePlan.objects.all()
        fields = ['id', 'name', 'description', 'visibility', 'edition', 'last_modified']
        resource_name = 'software_plan'


class DefaultProductPlanResource(ModelResource):
    plan = fields.IntegerField('plan', null=False)

    class Meta(AccountingResourceMeta):
        queryset = DefaultProductPlan.objects.all()
        fields = ['id', 'product_type', 'edition', 'is_trial', 'last_modified']
        resource_name = 'default_product_plan'


class SoftwareProductRateResource(ModelResource):
    product = fields.IntegerField('product_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = SoftwareProductRate.objects.all()
        fields = ['id', 'monthly_fee', 'date_created', 'is_active', 'last_modified']
        resource_name = 'software_product_rate'


class SoftwarePlanVersionResource(ModelResource):
    plan = fields.IntegerField('plan_id', null=True)
    product_rates = AccToManyField(FutureRateResource, 'product_rates', full=True, null=True)
    feature_rates = AccToManyField(FutureRateResource, 'feature_rates', full=True, null=True)
    role = fields.IntegerField('role_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = SoftwarePlanVersion.objects.all()
        fields = ['id', 'date_created', 'is_active', 'last_modified']
        resource_name = 'software_plan_versions'


class SubscriberResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Subscriber.objects.all()
        fields = ['id', 'domain', 'organization', 'last_modified']
        resource_name = 'subscriber'


class BillingContactInfoResource(ModelResource):
    account = fields.IntegerField('account_id')

    class Meta(AccountingResourceMeta):
        queryset = BillingContactInfo.objects.all()
        fields = ['id', 'first_name', 'last_name', 'emails', 'phone_number', 'company_name', 'first_line',
                  'second_line', 'city', 'state_province_region', 'postal_code', 'country', 'last_modified']
        resource_name = 'billing_contact_info'


class BillingAccountResource(ModelResource):
    currency = fields.IntegerField('currency_id', null=True)
    billing_contact_info = fields.ToOneField(BillingContactInfoResource,
                                             'billingcontactinfo',
                                             full=True,
                                             null=True)

    class Meta(AccountingResourceMeta):
        queryset = BillingAccount.objects.all()
        fields = ['id', 'name', 'salesforce_account_id', 'created_by', 'date_created', 'is_auto_invoiceable',
                  'account_type', 'created_by_domain', 'date_confirmed_extra_charges', 'is_active',
                  'dimagi_contact', 'entry_point', 'last_modified']
        resource_name = 'billing_account'


class SubscriptionResource(ModelResource):
    account = fields.IntegerField('account_id', null=True)
    plan_version = fields.IntegerField('plan_version_id', null=True)
    subscriber = fields.IntegerField('subscriber_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = Subscription.objects.all()
        fields = ['id', 'salesforce_contract_id', 'date_start', 'date_end', 'date_delay_invoicing',
                  'date_created', 'is_active', 'do_not_invoice', 'auto_generate_credits', 'is_trial',
                  'service_type', 'pro_bono_status', 'last_modified']
        resource_name = 'subscription'


class InvoiceResource(ModelResource):
    subscription = fields.IntegerField('subscription_id')
    subtotal = fields.DecimalField('subtotal')
    applied_credit = fields.DecimalField('applied_credit')

    class Meta(AccountingResourceMeta):
        queryset = Invoice.objects.all()
        fields = ['id', 'tax_rate', 'balance', 'date_due', 'date_paid', 'date_created', 'date_received',
                  'date_start', 'date_end', 'is_hidden', 'is_hidden_to_ops', 'last_modified']
        resource_name = 'invoice'


class LineItemResource(ModelResource):
    invoice = fields.IntegerField('invoice_id', null=True)
    feature_rate = fields.IntegerField('feature_rate_id', null=True)
    product_rate = fields.IntegerField('product_rate_id', null=True)
    subtotal = fields.DecimalField('subtotal')
    applied_credit = fields.DecimalField('applied_credit')

    class Meta(AccountingResourceMeta):
        queryset = LineItem.objects.all()
        fields = ['id', 'base_description', 'base_cost', 'unit_description', 'unit_cost', 'quantity',
                  'last_modified']
        resource_name = 'accounting_line_items'


class PaymentMethodResource(ModelResource):
    account = fields.IntegerField('account_id', null=True)
    web_user = fields.CharField('web_user', null=True)

    class Meta(AccountingResourceMeta):
        queryset = PaymentMethod.objects.all()
        fields = ['id', 'method_type', 'customer_id', 'date_created', 'last_modified']
        resource_name = 'accounting_payment_method'


class PaymentRecordResource(ModelResource):
    payment_method = fields.IntegerField('payment_method_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = PaymentRecord.objects.all()
        fields = ['id', 'date_created', 'transaction_id', 'amount', 'last_modified']
        resource_name = 'payment_record'


class CreditLineResource(ModelResource):
    account = fields.IntegerField('account_id', null=True)
    subscription = fields.IntegerField('subscription_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = CreditLine.objects.all()
        fields = ['id', 'product_type', 'feature_type', 'date_created', 'balance', 'is_active', 'last_modified']
        resource_name = 'credit_line'


class CreditAdjustmentResource(ModelResource):
    credit_line = fields.IntegerField('credit_line_id', null=True)
    line_item = fields.IntegerField('line_item_id', null=True)
    invoice = fields.IntegerField('invoice_id', null=True)
    payment_record = fields.IntegerField('payment_record_id', null=True)
    related_credit = fields.IntegerField('related_credit_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = CreditAdjustment.objects.all()
        fields = ['id', 'reason', 'note', 'amount', 'date_created', 'web_user', 'last_modified']
        resource_name = 'credit_adjustment'


class SubscriptionAndAdjustmentResource(ModelResource):

    subscription = fields.IntegerField('subscription_id', null=True)
    related_subscription = fields.IntegerField('related_subscription_id', null=True)
    invoice = fields.IntegerField('invoice_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = SubscriptionAdjustment.objects.all()
        fields = ['id', 'reason', 'method', 'note', 'web_user', 'invoice', 'date_created', 'new_date_start',
                  'new_date_end', 'new_date_delay_invoicing', 'new_salesforce_contract_id', 'last_modified']
        resource_name = 'subscription_and_adjustment'


class BillingRecordResource(ModelResource):
    invoice = fields.IntegerField('invoice_id', null=True)

    class Meta(AccountingResourceMeta):
        queryset = BillingRecord.objects.all()
        fields = ['id', 'date_created', 'emailed_to', 'pdf_data_id', 'skipped_email', 'last_modified']
        resource_name = 'billing_record'
