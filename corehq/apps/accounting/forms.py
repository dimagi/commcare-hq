from corehq import Domain
from corehq.apps.accounting.models import *
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import *
from django import forms


class BillingAccountForm(forms.Form):
    name = forms.CharField(label="Name")
    salesforce_account_id = forms.CharField(label="Salesforce ID", required=False)
    currency = forms.ChoiceField(label="Currency")

    billing_account_admins = forms.CharField(label='Billing Account Admins',required=False)
    first_name = forms.CharField(label='First Name', required=False)
    last_name = forms.CharField(label='Last Name', required=False)
    company_name = forms.CharField(label='Company Name', required=False)
    phone_number = forms.CharField(label='Phone Number', required=False)
    address_line_1 = forms.CharField(label='Address Line 1')
    address_line_2 = forms.CharField(label='Address Line 2', required=False)
    city = forms.CharField()
    region = forms.CharField(label="State/Province/Region")
    postal_code = forms.CharField(label="Postal Code")
    country = forms.CharField()

    def __init__(self, account, *args, **kwargs):
        if account is not None:
            contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
            kwargs['initial'] = {'name': account.name,
                                 'salesforce_account_id': account.salesforce_account_id,
                                 'currency': account.currency.code,
                                 'billing_account_admins':
                                     ', '.join([admin.web_user for admin in account.billing_admins.all()]),
                                 'first_name': contact_info.first_name,
                                 'last_name': contact_info.last_name,
                                 'company_name': contact_info.company_name,
                                 'phone_number': contact_info.phone_number,
                                 'address_line_1': contact_info.first_line,
                                 'address_line_2': contact_info.second_line,
                                 'city': contact_info.city,
                                 'region': contact_info.state_province_region,
                                 'postal_code': contact_info.postal_code,
                                 'country': contact_info.country,
                                 }
        else:
            kwargs['initial'] = {'currency': Currency.get_default().code,
                                 }
        super(BillingAccountForm, self).__init__(*args, **kwargs)
        if account is None:
            self.fields['address_line_1'].required = False
            self.fields['city'].required = False
            self.fields['region'].required = False
            self.fields['postal_code'].required = False
            self.fields['country'].required = False
        self.fields['currency'].choices =\
            [(cur.code, cur.code) for cur in Currency.objects.order_by('code')]
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            'Basic Information',
                'name',
                'salesforce_account_id',
                'currency',
            ),
            Fieldset(
            'Contact Information',
                'billing_account_admins',
                'first_name',
                'last_name',
                'company_name',
                'phone_number',
                'address_line_1',
                'address_line_2',
                'city',
                'region',
                'postal_code',
                'country',
            ) if account is not None else None,
            FormActions(
                ButtonHolder(
                    Submit('account', 'Update Account' if account is not None else 'Add New Account')
                )
            )
        )


class SubscriptionForm(forms.Form):
    start_date = forms.DateField(label="Start Date", widget=forms.DateInput())
    end_date = forms.DateField(label="End Date", widget=forms.DateInput(), required=False)
    delay_invoice_until = forms.DateField(label="Delay Invoice Until", widget=forms.DateInput(), required=False)
    plan = forms.ChoiceField()
    domain = forms.CharField(max_length=25)
    salesforce_contract_id = forms.CharField(label="Salesforce Contract ID", max_length=80, required=False)

    def __init__(self, subscription, *args, **kwargs):
        super(SubscriptionForm, self).__init__(*args, **kwargs)

        css_class = {'css_class': 'date-picker'}
        disabled = {'disabled': 'disabled'}

        start_date_kwargs = dict(**css_class)
        end_date_kwargs = dict(**css_class)
        delay_invoice_until_kwargs = dict(**css_class)
        plan_kwargs = dict()
        domain_kwargs = dict()

        self.fields['plan'].choices = [(plan.id, str(plan)) for plan in SoftwarePlanVersion.objects.all()]
        if subscription is not None:
            self.fields['start_date'].initial = subscription.date_start
            self.fields['end_date'].initial = subscription.date_end
            self.fields['delay_invoice_until'].initial = subscription.date_delay_invoicing
            self.fields['plan'].initial = subscription.plan.id
            self.fields['domain'].initial = subscription.subscriber.domain
            if subscription.date_start is not None \
                and subscription.date_start <= datetime.date.today():
                start_date_kwargs.update(disabled)
                self.fields['start_date'].required = False
            if subscription.date_end is not None \
                and subscription.date_end <= datetime.date.today():
                end_date_kwargs.update(disabled)
            if subscription.date_delay_invoicing is not None \
                and subscription.date_delay_invoicing <= datetime.date.today():
                delay_invoice_until_kwargs.update(disabled)
            plan_kwargs.update(disabled)
            self.fields['plan'].required = False
            domain_kwargs.update(disabled)
            self.fields['domain'].required = False
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            '%s Subscription' % ('Edit' if subscription is not None else 'New'),
                Field('start_date', **start_date_kwargs),
                Field('end_date', **end_date_kwargs),
                Field('delay_invoice_until', **delay_invoice_until_kwargs),
                Field('plan', **plan_kwargs),
                Field('domain', **domain_kwargs),
                'salesforce_contract_id',
            ),
            FormActions(
                ButtonHolder(
                    Submit('set_subscription', 'Submit')
                )
            )
        )

    def clean_domain(self):
        domain_name = self.cleaned_data['domain']
        domain = Domain.get_by_name(domain_name)
        if domain is None:
            raise forms.ValidationError("A valid project space is required.")
        return domain_name


class CreditForm(forms.Form):
    amount = forms.DecimalField()
    note = forms.CharField(required=False)
    rate_type = forms.ChoiceField(choices=(('Any', 'Any'),
                                           ('Product', 'Product'),
                                           ('Feature', 'Feature')))
    product = forms.ChoiceField()
    feature = forms.ChoiceField(label="Rate")

    def __init__(self, id, is_account, *args, **kwargs):
        super(CreditForm, self).__init__(*args, **kwargs)
        if not kwargs:
            self.fields['product'].choices = self.get_product_choices(id, is_account)
            self.fields['feature'].choices = self.get_feature_choices(id, is_account)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            'Adjust %s Credit' % 'Account Level' if is_account else 'Subscription Level',
                'amount',
                'note',
                Field('rate_type', data_bind="value: rateType"),
                Div('product', data_bind="visible: showProduct"),
                Div('feature', data_bind="visible: showFeature"),
            ),
            FormActions(
                ButtonHolder(
                    Submit('adjust_credit', 'Submit')
                )
            )
        )

    def get_subscriptions(self, id, is_account):
        return Subscription.objects.filter(account=BillingAccount.objects.get(id=id))\
            if is_account else [Subscription.objects.get(id=id)]

    def get_product_choices(self, id, is_account):
        subscriptions = self.get_subscriptions(id, is_account)
        product_rate_sets = [sub.plan.product_rates for sub in subscriptions]
        products = set()
        for product_rate_set in product_rate_sets:
            for product_rate in product_rate_set.all():
                products.add(product_rate.product)
        return [(product.id, product.name) for product in products]

    def get_feature_choices(self, id, is_account):
        subscriptions = self.get_subscriptions(id, is_account)
        feature_rate_sets = [sub.plan.feature_rates for sub in subscriptions]
        features = set()
        for feature_rate_set in feature_rate_sets:
            for feature_rate in feature_rate_set.all():
                features.add(feature_rate.feature)
        return [(feature.id, feature.name) for feature in features]


class CancelForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(CancelForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        cancel_subscription_button = Button('cancel_subscription', 'CANCEL SUBSCRIPTION', css_class="btn-danger")
        cancel_subscription_button.input_type = 'submit'
        self.helper.layout = Layout(
            ButtonHolder(
                cancel_subscription_button
            )
        )
