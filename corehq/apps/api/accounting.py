from tastypie.resources import ModelResource
from corehq.apps.accounting.models import Feature, FeatureRate, SoftwarePlanVersion, LineItem, PaymentMethod, \
    BillingAccountAdmin, BillingAccount, BillingContactInfo, Currency, PaymentRecord, SoftwareProductRate, \
    SoftwareProduct, SoftwarePlan, DefaultProductPlan, CreditAdjustment, Subscription, CreditLine, Subscriber, \
    SubscriptionAdjustment, BillingRecord, Invoice
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, SuperuserAuthentication
from tastypie import fields
from django_prbac.models import Role


class AccountingResourceMeta(CustomResourceMeta):
    authentication = SuperuserAuthentication()
    list_allowed_methods = ['get']
    include_resource_uri = False


class FeatureResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Feature.objects.all()
        fields = ['id', 'name', 'feature_type']
        resource_name = 'accounting_features'


class FutureRateResource(ModelResource):
    feature = fields.ToOneField(FeatureResource, 'feature', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = FeatureRate.objects.all()
        fields = ['id', 'monthly_fee', 'monthly_limit',
                  'per_excess_fee', 'date_created', 'is_active']
        resource_name = 'accounting_feature_rates'


class RoleResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Role.objects.all()
        fields = ['id', 'slug', 'name', 'description', 'parameters']
        resource_name = 'role'


class BillingAccountAdminResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = BillingAccountAdmin.objects.all()
        fields = ['id', 'web_user', 'domain']
        resource_name = 'billing_account_admin'


class AccountingCurrencyResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Currency.objects.all()
        fields = ['id', 'code', 'name', 'symbol', 'rate_to_default', 'date_updated']
        resource_name = 'accounting_currency'


class SoftwareProductResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = SoftwareProduct.objects.all()
        fields = ['id', 'name', 'product_type']
        resource_name = 'software_product'


class SoftwarePlanResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = SoftwarePlan.objects.all()
        fields = ['id', 'name', 'description', 'visibility', 'edition']
        resource_name = 'software_plan'


class DefaultProductPlanResource(ModelResource):
    plan = fields.ToOneField(SoftwarePlanResource, 'plan', full=True, null=False)

    class Meta(AccountingResourceMeta):
        queryset = DefaultProductPlan.objects.all()
        fields = ['id', 'product_type', 'edition', 'is_trial']
        resource_name = 'default_product_plan'


class SoftwareProductRateResource(ModelResource):
    product = fields.ToOneField(SoftwareProductResource, 'product', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = SoftwareProductRate.objects.all()
        fields = ['id', 'monthly_fee', 'date_created', 'is_active']
        resource_name = 'software_product_rate'


class SoftwarePlanVersionResource(ModelResource):
    plan = fields.ToOneField(SoftwarePlanResource, 'plan', full=True, null=True)
    product_rates = fields.ToOneField(SoftwareProductRateResource, 'product_rate', full=True, null=True)
    feature_rates = fields.ToManyField(FutureRateResource, 'feature_rates', full=True, null=True)
    role = fields.ToOneField(RoleResource, 'role', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = SoftwarePlanVersion.objects.all()
        fields = ['id', 'date_created', 'is_active']
        resource_name = 'software_plan_versions'


class SubscriberResource(ModelResource):

    class Meta(AccountingResourceMeta):
        queryset = Subscriber.objects.all()
        fields = ['id', 'domain', 'organization']
        resource_name = 'subscriber'


class BillingAccountResource(ModelResource):
    currency = fields.ToOneField(AccountingCurrencyResource, 'currency', full=True, null=True)
    billing_admins = fields.ToManyField(BillingAccountAdminResource, 'billing_admins', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = BillingAccount.objects.all()
        fields = ['id', 'name', 'salesforce_account_id', 'created_by', 'date_created', 'is_auto_invoiceable',
                  'account_type', 'created_by_domain', 'date_confirmed_extra_charges', 'is_active',
                  'dimagi_contact', 'entry_point']
        resource_name = 'billing_account'


class SubscriptionResource(ModelResource):
    account = fields.ToOneField(BillingAccountResource, 'acount', full=True, null=True)
    plan_version = fields.ToOneField(SoftwarePlanVersionResource, 'plan_version', full=True, null=True)
    subscriber = fields.ToOneField(SubscriberResource, 'subscriber', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = Subscription.objects.all()
        fields = ['id', 'salesforce_contract_id', 'date_start', 'date_end', 'date_delay_invoicing',
                  'date_created', 'is_active', 'do_not_invoice', 'auto_generate_credits', 'is_trial',
                  'service_type', 'pro_bono_status']
        resource_name = 'subscription'


class InvoiceResource(ModelResource):
    subscription = fields.ToOneField(SubscriptionResource, 'subscription', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = Invoice.objects.all()
        fields = ['id', 'tax_rate', 'balance', 'date_due', 'date_paid', 'date_created', 'date_received',
                  'date_start', 'date_end', 'is_hidden', 'is_hidden_to_ops']
        resource_name = 'invoice'


class LineItemResource(ModelResource):
    invoice = fields.ToOneField(InvoiceResource, 'invoice', full=True, null=True)
    feature_rates = fields.ToManyField(FutureRateResource, 'feature_rates', full=True, null=True)
    product_rate = fields.ToOneField(SoftwareProductRateResource, 'product_rate', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = LineItem.objects.all()
        fields = ['id', 'base_description', 'base_cost', 'unit_description', 'unit_cost', 'quantity']
        resource_name = 'accounting_line_items'


class PaymentMethodResource(ModelResource):
    account = fields.ToOneField(BillingAccountResource, 'account', full=True, null=True)
    billing_admin = fields.ToOneField(BillingAccountAdminResource, 'billing_admin', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = PaymentMethod.objects.all()
        fields = ['id', 'method_type', 'customer_id', 'date_created']
        resource_name = 'accounting_payment_method'


class BillingContactInfoResource(ModelResource):
    account = fields.ToOneField(BillingAccountResource, 'account', full=True, null=False)

    class Meta(AccountingResourceMeta):
        queryset = BillingContactInfo.objects.all()
        fields = ['id', 'first_name', 'last_name', 'emails', 'phone_number', 'company_name', 'first_line',
                  'second_line', 'city', 'state_province_region', 'postal_code', 'country']
        resource_name = 'billing_contact_info'


class PaymentRecordResource(ModelResource):
    payment_method = fields.ToOneField(PaymentMethodResource, 'payment_method', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = PaymentRecord.objects.all()
        fields = ['id', 'date_created', 'transaction_id', 'amount']
        resource_name = 'payment_record'


class CreditLineResource(ModelResource):
    account = fields.ToOneField(BillingAccountResource, 'account', full=True, null=True)
    subscription = fields.ToOneField(SubscriptionResource, 'subscription', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = CreditLine.objects.all()
        fields = ['id', 'product_type', 'feature_type', 'date_created', 'balance', 'is_active']
        resource_name = 'credit_line'


class CreditAdjustmentResource(ModelResource):
    credit_line = fields.ToOneField(CreditLineResource, 'credit_line', full=True, null=True)
    line_item = fields.ToOneField(LineItemResource, 'line_item', full=True, null=True)
    invoice = fields.ToOneField(InvoiceResource, 'invoice', full=True, null=True)
    payment_record = fields.ToOneField(PaymentRecordResource, 'payment_record', full=True, null=True)
    related_credit = fields.ToOneField(CreditLineResource, 'related_credit', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = CreditAdjustment.objects.all()
        fields = ['id', 'reason', 'note', 'amount', 'date_created', 'web_user']
        resource_name = 'credit_adjustment'


class SubscriptionAndAdjustmentResource(ModelResource):

    subscription = fields.ToOneField(SubscriptionResource, 'subscription', full=True, null=True)
    related_subscription = fields.ToOneField(SubscriptionResource, 'related_subscription', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = SubscriptionAdjustment.objects.all()
        fields = ['id', 'reason', 'method', 'note', 'web_user', 'invoice', 'date_created', 'new_date_start',
                  'new_date_end', 'new_date_delay_invoicing', 'new_salesforce_contract_id']
        resource_name = 'subscription_and_adjustment'


class BillingRecordResource(ModelResource):
    invoice = fields.ToOneField(InvoiceResource, 'invoice', full=True, null=True)

    class Meta(AccountingResourceMeta):
        queryset = BillingRecord.objects.all()
        fields = ['id', 'date_created', 'emailed_to', 'pdf_data_id', 'skipped_email']
        resource_name = 'billing_record'
