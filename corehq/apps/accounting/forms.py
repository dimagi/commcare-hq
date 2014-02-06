import datetime
import json
from django.conf import settings

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django import forms
from django.core.urlresolvers import reverse
from django.forms.util import ErrorList
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop, ugettext as _, ugettext

from crispy_forms.bootstrap import FormActions, StrictButton, InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.email import send_HTML_email
from django_prbac.models import Role

from corehq.apps.accounting.async_handlers import (FeatureRateAsyncHandler, SoftwareProductRateAsyncHandler,
                                                   RoleAsyncHandler, Select2RateAsyncHandler)
from corehq.apps.accounting.utils import fmt_feature_rate_dict, fmt_product_rate_dict, fmt_role_dict
from corehq.apps.hqwebapp.crispy import BootstrapMultiField
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.apps.accounting.models import (BillingContactInfo, Currency, SoftwarePlanVersion, BillingAccount,
                                           Subscription, Subscriber, CreditLine, SoftwareProductRate,
                                           FeatureRate, SoftwarePlanEdition, SoftwarePlanVisibility,
                                           BillingAccountAdmin, SoftwarePlan, Feature, FeatureType,
                                           SoftwareProduct, SoftwareProductType)


class BillingAccountForm(forms.Form):
    name = forms.CharField(label="Name")
    salesforce_account_id = forms.CharField(label="Salesforce ID", required=False)
    currency = forms.ChoiceField(label="Currency")

    billing_account_admins = forms.CharField(label='Billing Account Admins', required=False)
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
            kwargs['initial'] = {
                'name': account.name,
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
            kwargs['initial'] = {
                'currency': Currency.get_default().code,
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
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
            'Basic Information',
                'name',
                'salesforce_account_id',
                'currency',
            ),
            crispy.Fieldset(
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
                crispy.ButtonHolder(
                    crispy.Submit('account', 'Update Account' if account is not None else 'Add New Account')
                )
            )
        )

    def clean_billing_account_admins(self):
        billing_account_admins = self.cleaned_data['billing_account_admins']
        if billing_account_admins != '':
            invalid_emails = []
            for email in billing_account_admins.split(','):
                email_no_whitespace = email.strip()
                if WebUser.get_by_username(email_no_whitespace) is None:
                    invalid_emails.append("'%s'" % email_no_whitespace)
            if len(invalid_emails) != 0:
                raise ValidationError("Invalid emails: %s" % ', '.join(invalid_emails))
        return billing_account_admins

    def create_account(self):
        name = self.cleaned_data['name']
        salesforce_account_id = self.cleaned_data['salesforce_account_id']
        currency, _ = Currency.objects.get_or_create(code=self.cleaned_data['currency'])
        account = BillingAccount(name=name,
                                 salesforce_account_id=salesforce_account_id,
                                 currency=currency)
        account.save()
        return account

    def update_account_and_contacts(self, account):
        account.name = self.cleaned_data['name']
        account.salesforce_account_id = self.cleaned_data['salesforce_account_id']
        account.currency, _ = Currency.objects.get_or_create(code=self.cleaned_data['currency'])
        for web_user_email in self.cleaned_data['billing_account_admins'].split(','):
            admin, _ = BillingAccountAdmin.objects.get_or_create(web_user=web_user_email)
            account.billing_admins.add(admin)
        account.save()

        contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
        contact_info.first_name = self.cleaned_data['first_name']
        contact_info.last_name = self.cleaned_data['last_name']
        contact_info.company_name = self.cleaned_data['company_name']
        contact_info.phone_number = self.cleaned_data['phone_number']
        contact_info.first_line = self.cleaned_data['address_line_1']
        contact_info.second_line = self.cleaned_data['address_line_2']
        contact_info.city = self.cleaned_data['city']
        contact_info.state_province_region = self.cleaned_data['region']
        contact_info.postal_code = self.cleaned_data['postal_code']
        contact_info.country = self.cleaned_data['country']
        contact_info.save()


class SubscriptionForm(forms.Form):
    start_date = forms.DateField(label="Start Date", widget=forms.DateInput())
    end_date = forms.DateField(label="End Date", widget=forms.DateInput(), required=False)
    delay_invoice_until = forms.DateField(label="Delay Invoice Until", widget=forms.DateInput(), required=False)
    plan_version = forms.ChoiceField(label="Plan Version")
    domain = forms.CharField(max_length=25)
    salesforce_contract_id = forms.CharField(label="Salesforce Contract ID", max_length=80, required=False)

    def __init__(self, subscription, *args, **kwargs):
        super(SubscriptionForm, self).__init__(*args, **kwargs)

        css_class = {'css_class': 'date-picker'}
        disabled = {'disabled': 'disabled'}

        start_date_kwargs = dict(**css_class)
        end_date_kwargs = dict(**css_class)
        delay_invoice_until_kwargs = dict(**css_class)
        domain_kwargs = dict()

        if subscription is not None:
            self.fields['plan_version'].choices = [(subscription.plan_version.id,
                                                    str(subscription.plan_version))]
            self.fields['start_date'].initial = subscription.date_start
            self.fields['end_date'].initial = subscription.date_end
            self.fields['delay_invoice_until'].initial = subscription.date_delay_invoicing
            self.fields['plan_version'].initial = subscription.plan_version.id
            self.fields['domain'].initial = subscription.subscriber.domain
            self.fields['salesforce_contract_id'].initial = subscription.salesforce_contract_id
            if (subscription.date_start is not None
                and subscription.date_start <= datetime.date.today()):
                start_date_kwargs.update(disabled)
                self.fields['start_date'].required = False
            if (subscription.date_end is not None
                and subscription.date_end <= datetime.date.today()):
                end_date_kwargs.update(disabled)
            if (subscription.date_delay_invoicing is not None
                and subscription.date_delay_invoicing <= datetime.date.today()):
                delay_invoice_until_kwargs.update(disabled)
            self.fields['plan_version'].required = False
            domain_kwargs.update(disabled)
            self.fields['domain'].required = False
        else:
            self.fields['plan_version'].choices = [(plan_version.id, str(plan_version))
                                                   for plan_version in SoftwarePlanVersion.objects.all()]
        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
            '%s Subscription' % ('Edit' if subscription is not None else 'New'),
                crispy.Field('start_date', **start_date_kwargs),
                crispy.Field('end_date', **end_date_kwargs),
                crispy.Field('delay_invoice_until', **delay_invoice_until_kwargs),
                crispy.Field('plan_version'),
                crispy.Field('domain', **domain_kwargs),
                'salesforce_contract_id',
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit('set_subscription',
                           '%s Subscription' % ('Update' if subscription is not None else 'Create'))
                )
            )
        )

    def clean_domain(self):
        domain_name = self.cleaned_data['domain']
        if self.fields['domain'].required:
            domain = Domain.get_by_name(domain_name)
            if domain is None:
                raise forms.ValidationError("A valid project space is required.")
        return domain_name

    def create_subscription(self, account_id):
        account = BillingAccount.objects.get(id=account_id)
        date_start = self.cleaned_data['start_date']
        date_end = self.cleaned_data['end_date']
        date_delay_invoicing = self.cleaned_data['delay_invoice_until']
        plan_version_id = self.cleaned_data['plan_version']
        domain = self.cleaned_data['domain']
        subscription = Subscription(account=account,
                                    date_start=date_start,
                                    date_end=date_end,
                                    date_delay_invoicing=date_delay_invoicing,
                                    plan_version=SoftwarePlanVersion.objects.get(id=plan_version_id),
                                    salesforce_contract_id=self.cleaned_data['salesforce_contract_id'],
                                    subscriber=Subscriber.objects.get_or_create(domain=domain,
                                                                                organization=None)[0])
        subscription.save()
        return subscription

    def update_subscription(self, subscription):
        if self.fields['start_date'].required:
            subscription.date_start = self.cleaned_data['start_date']
        if subscription.date_end is None or subscription.date_end > datetime.date.today():
            subscription.date_end = self.cleaned_data['end_date']
        if (subscription.date_delay_invoicing is None
            or subscription.date_delay_invoicing > datetime.date.today()):
            subscription.date_delay_invoicing = self.cleaned_data['delay_invoice_until']
        subscription.salesforce_contract_id = self.cleaned_data['salesforce_contract_id']
        subscription.save()


class CreditForm(forms.Form):
    amount = forms.DecimalField()
    note = forms.CharField(required=False)
    rate_type = forms.ChoiceField()
    product_rate = forms.ChoiceField(required=False, label=_("Product Rate"))
    feature_rate = forms.ChoiceField(required=False, label=_("Feature Rate"))

    def __init__(self, id, is_account, *args, **kwargs):
        super(CreditForm, self).__init__(*args, **kwargs)
        if not kwargs:
            self.fields['product_rate'].choices = self.get_product_rate_choices(id, is_account)
            self.fields['feature_rate'].choices = self.get_feature_choices(id, is_account)
            self.fields['rate_type'].choices = self.get_rate_type_choices(self.fields['product_rate'].choices,
                                                                          self.fields['feature_rate'].choices)
        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
            'Adjust %s Level Credit' % ('Account' if is_account else 'Subscription'),
                'amount',
                'note',
                crispy.Field('rate_type', data_bind="value: rateType"),
                crispy.Div('product_rate', data_bind="visible: showProduct"),
                crispy.Div('feature_rate', data_bind="visible: showFeature"),
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit('adjust_credit', 'Update Credit')
                )
            )
        )

    def get_subscriptions(self, id, is_account):
        return Subscription.objects.filter(account=BillingAccount.objects.get(id=id))\
            if is_account else [Subscription.objects.get(id=id)]

    def get_product_rate_choices(self, id, is_account):
        subscriptions = self.get_subscriptions(id, is_account)
        product_rate_sets = [sub.plan_version.product_rates for sub in subscriptions]
        product_rates = set()
        for product_rate_set in product_rate_sets:
            for product_rate in product_rate_set.all():
                product_rates.add(product_rate)
        return [(product_rate.id, str(product_rate)) for product_rate in product_rates]

    def get_feature_choices(self, id, is_account):
        subscriptions = self.get_subscriptions(id, is_account)
        feature_rate_sets = [sub.plan_version.feature_rates for sub in subscriptions]
        feature_rates = set()
        for feature_rate_set in feature_rate_sets:
            for feature_rate in feature_rate_set.all():
                feature_rates.add(feature_rate)
        return [(feature_rate.id, str(feature_rate)) for feature_rate in feature_rates]

    def get_rate_type_choices(self, product_choices, feature_choices):
        choices = [('Any', 'Any')]
        if len(product_choices) != 0:
            choices.append(('Product', 'Product'))
        if len(feature_choices) != 0:
            choices.append(('Feature', 'Feature'))
        return choices

    def adjust_credit(self, account=None, subscription=None):
        amount = self.cleaned_data['amount']
        note = self.cleaned_data['note']

        def get_account_for_rate():
            return account if account is not None else subscription.account

        def add_product_rate():
            CreditLine.add_rate_credit(amount, get_account_for_rate(),
                                       product_rate=SoftwareProductRate.objects.get(
                                           id=self.cleaned_data['product_rate']),
                                       subscription=subscription,
                                       note=note)

        def add_feature_rate():
            CreditLine.add_rate_credit(amount, get_account_for_rate(),
                                       feature_rate=FeatureRate.objects.get(
                                           id=self.cleaned_data['feature_rate']),
                                       subscription=subscription,
                                       note=note)

        def add_account_level():
            CreditLine.add_account_credit(amount, account,
                                          note=note)

        def add_subscription_level():
            CreditLine.add_subscription_credit(amount, subscription,
                                               note=note)

        if self.cleaned_data['rate_type'] == 'Product':
            add_product_rate()
        elif self.cleaned_data['rate_type'] == 'Feature':
            add_feature_rate()
        elif account is not None:
            add_account_level()
        elif subscription is not None:
            add_subscription_level()
        else:
            raise ValueError('invalid credit adjustment')


class CancelForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(CancelForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        cancel_subscription_button = crispy.Button('cancel_subscription', 'CANCEL SUBSCRIPTION', css_class="btn-danger")
        cancel_subscription_button.input_type = 'submit'
        self.helper.layout = crispy.Layout(
            crispy.ButtonHolder(
                cancel_subscription_button
            )
        )


class PlanInformationForm(forms.Form):
    name = forms.CharField(max_length=80)
    description = forms.CharField(required=False)
    edition = forms.ChoiceField(choices=SoftwarePlanEdition.CHOICES)
    visibility = forms.ChoiceField(choices=SoftwarePlanVisibility.CHOICES)

    def __init__(self, plan, *args, **kwargs):
        self.plan = plan
        if plan is not None:
            kwargs['initial'] = {
                'name': plan.name,
                'description': plan.description,
                'edition': plan.edition,
                'visibility': plan.visibility,
            }
        else:
            kwargs['initial'] = {
                'edition': SoftwarePlanEdition.ENTERPRISE,
                'visibility': SoftwarePlanVisibility.INTERNAL,
            }
        super(PlanInformationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
            'Plan Information',
                'name',
                'description',
                'edition',
                'visibility',
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit('plan_information',
                           '%s Software Plan' % ('Update' if plan is not None else 'Create'))
                )
            )
        )

    def clean_name(self):
        name = self.cleaned_data['name']
        if (len(SoftwarePlan.objects.filter(name=name)) != 0
            and (self.plan is None or self.plan.name != name)):
            raise ValidationError('Name already taken.  Please enter a new name.')
        return name

    def create_plan(self):
        name = self.cleaned_data['name']
        description = self.cleaned_data['description']
        edition = self.cleaned_data['edition']
        visibility = self.cleaned_data['visibility']
        plan = SoftwarePlan(name=name,
                            description=description,
                            edition=edition,
                            visibility=visibility)
        plan.save()
        return plan

    def update_plan(self, plan):
        plan.name = self.cleaned_data['name']
        plan.description = self.cleaned_data['description']
        plan.edition = self.cleaned_data['edition']
        plan.visibility = self.cleaned_data['visibility']
        plan.save()


class SoftwarePlanVersionForm(forms.Form):
    """
    A form for updating the software plan
    """
    update_version = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    feature_id = forms.CharField(
        required=False,
        label="Search for or Create Feature"
    )
    new_feature_type = forms.ChoiceField(
        required=False,
        choices=FeatureType.CHOICES,
    )
    feature_rates = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    product_id = forms.CharField(
        required=False,
        label="Search for or Create Product"
    )
    new_product_type = forms.ChoiceField(
        required=False,
        choices=SoftwareProductType.CHOICES,
    )
    product_rates = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    privileges = forms.MultipleChoiceField(
        label="Privileges",
        validators=[MinLengthValidator(1)]
    )
    new_role_slug = forms.CharField(
        required=False
    )

    def __init__(self, plan, plan_version, *args, **kwargs):
        self.plan = plan
        self.plan_version = plan_version
        data = {}
        if self.plan_version is not None:
            data['feature_rates'] = json.dumps([fmt_feature_rate_dict(r.feature, r)
                                                for r in self.plan_version.feature_rates.all()])
            data['product_rates'] = json.dumps([fmt_product_rate_dict(r.product, r)
                                                for r in self.plan_version.product_rates.all()])
        else:
            data['feature_rates'] = json.dumps([])
            data['product_rates'] = json.dumps([])
            data['role'] = json.dumps([])

        self.is_update = False

        super(SoftwarePlanVersionForm, self).__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            'update_version',
            crispy.Fieldset(
                "Permissions",
                # InlineField('privileges', data_bind="value: roles.objectsValue"),
                BootstrapMultiField(
                    "Privileges",
                    # InlineField('privileges', css_class="input-xxlarge",
                    #             data_bind="value: role.select2.value"),
                    # StrictButton(
                    #     "Select Role",
                    #     css_class="btn-primary",
                    #     data_bind="event: {click: role.apply}, "
                    #               "visible: role.select2.isExisting",
                    #     style="margin-left: 5px;"
                    # ),
                ),
                # crispy.Div(
                #     css_class="alert alert-error",
                #     data_bind="text: privileges.error, visible: privileges.showError"
                # ),
                # BootstrapMultiField(
                #     "Role Slug",
                #     InlineField(
                #         'new_role_slug',
                #         data_bind="value: role.slug"
                #     ),
                #     Div(
                #         StrictButton(
                #             "Create Role",
                #             css_class="btn-success",
                #             data_bind="event: {click: role.createNew}",
                #         ),
                #         style="margin: 10px 0;"
                #     ),
                #     data_bind="visible: role.select2.isNew",
                # ),
                # Div(
                #     data_bind="template: {"
                #               "name: 'role-form-template', foreach: role.objects"
                #               "}",
                # ),
            ),
            crispy.Fieldset(
                "Features",
                InlineField('feature_rates', data_bind="value: featureRates.objectsValue"),
                BootstrapMultiField(
                    "Add Feature",
                    InlineField('feature_id', css_class="input-xxlarge",
                                data_bind="value: featureRates.select2.value"),
                    StrictButton(
                        "Select Feature",
                        css_class="btn-primary",
                        data_bind="event: {click: featureRates.apply}, "
                                  "visible: featureRates.select2.isExisting",
                        style="margin-left: 5px;"
                    ),
                ),
                crispy.Div(
                    css_class="alert alert-error",
                    data_bind="text: featureRates.error, visible: featureRates.showError"
                ),
                BootstrapMultiField(
                    "Feature Type",
                    InlineField(
                        'new_feature_type',
                        data_bind="value: featureRates.rateType",
                    ),
                    crispy.Div(
                        StrictButton(
                            "Create Feature",
                            css_class="btn-success",
                            data_bind="event: {click: featureRates.createNew}",

                        ),
                        style="margin: 10px 0;"
                    ),
                    data_bind="visible: featureRates.select2.isNew",
                ),
                crispy.Div(
                    data_bind="template: {"
                              "name: 'feature-rate-form-template', foreach: featureRates.objects"
                              "}",
                ),
            ),
            crispy.Fieldset(
                "Products",
                InlineField('product_rates', data_bind="value: productRates.objectsValue"),
                BootstrapMultiField(
                    "Add Product",
                    InlineField('product_id', css_class="input-xxlarge",
                                data_bind="value: productRates.select2.value"),
                    StrictButton(
                        "Select Product",
                        css_class="btn-primary",
                        data_bind="event: {click: productRates.apply}, "
                                  "visible: productRates.select2.isExisting",
                        style="margin-left: 5px;"
                    ),
                ),
                crispy.Div(
                    css_class="alert alert-error",
                    data_bind="text: productRates.error, visible: productRates.showError",
                ),
                BootstrapMultiField(
                    "Product Type",
                    InlineField(
                        'new_product_type',
                        data_bind="value: productRates.rateType",
                    ),
                    crispy.Div(
                        StrictButton(
                            "Create Product",
                            css_class="btn-success",
                            data_bind="event: {click: productRates.createNew}",
                        ),
                        style="margin: 10px 0;"
                    ),
                    data_bind="visible: productRates.select2.isNew",
                ),
                crispy.Div(
                    data_bind="template: {"
                              "name: 'product-rate-form-template', foreach: productRates.objects"
                              "}",
                ),
            ),
            FormActions(
                StrictButton(
                    'Update Plan Version',
                    css_class='btn-primary',
                    type="submit",
                ),
            )
        )

    @property
    def feature_rates_dict(self):
        return {
            'currentValue': self['feature_rates'].value(),
            'handlerSlug': FeatureRateAsyncHandler.slug,
            'select2Options': {
                'fieldName': 'feature_id',
            }
        }

    @property
    def product_rates_dict(self):
        return {
            'currentValue': self['product_rates'].value(),
            'handlerSlug': SoftwareProductRateAsyncHandler.slug,
            'select2Options': {
                'fieldName': 'product_id',
            }
        }

    @property
    def role_dict(self):
        return {
            'currentValue': self['privileges'].value(),
            'select2Options': {
                'fieldName': 'privileges',
                'multiple': True,
            }
        }

    @property
    @memoized
    def current_features_to_rates(self):
        return dict([(r.feature.id, r) for r in self.plan_version.feature_rates.all()])

    @property
    @memoized
    def current_products_to_rates(self):
        return dict([(r.product.id, r) for r in self.plan_version.product_rates.all()])

    def _get_errors_from_subform(self, form_name, subform):
        for field, field_errors in subform._errors.items():
            for field_error in field_errors:
                error_message = "%(form_name)s > %(field_name)s: %(error)s" % {
                    'form_name': form_name,
                    'error': field_error,
                    'field_name': subform[field].label,
                }
                yield error_message

    def _retrieve_feature_rate(self, rate_form):
        feature = Feature.objects.get(id=rate_form['feature_id'].value())
        new_rate = rate_form.get_instance(feature)
        if rate_form.is_new():
            # a brand new rate
            self.is_update = True
            return new_rate
        if feature.id not in self.current_features_to_rates.keys():
            # the plan does not have this rate yet, compare any changes to the feature's current latest rate
            # also mark the form as updated
            current_rate = feature.get_rate(default_instance=False)
            if current_rate is None:
                return new_rate
            self.is_update = True
        else:
            current_rate = self.current_features_to_rates[feature.id]
        # note: custom implementation of FeatureRate.__eq__ here...
        if not current_rate == new_rate:
            self.is_update = True
            return new_rate
        return current_rate

    def _retrieve_product_rate(self, rate_form):
        product = SoftwareProduct.objects.get(id=rate_form['product_id'].value())
        new_rate = rate_form.get_instance(product)
        if rate_form.is_new():
            # a brand new rate
            self.is_update = True
            return new_rate
        if product.id not in self.current_products_to_rates.keys():
            # the plan does not have this rate yet, compare any changes to the feature's current latest rate
            # also mark the form as updated
            current_rate = product.get_rate(default_instance=False)
            if current_rate is None:
                return new_rate
            self.is_update = True
        else:
            current_rate = self.current_products_to_rates[product.id]
        # note: custom implementation of SoftwareProductRate.__eq__ here...
        if not current_rate == new_rate:
            self.is_update = True
            return new_rate
        return current_rate

    def clean_feature_rates(self):
        original_data = self.cleaned_data['feature_rates']
        rates = json.loads(original_data)
        rate_instances = []
        errors = ErrorList()
        for rate_data in rates:
            rate_form = FeatureRateForm(rate_data)
            if not rate_form.is_valid():
                errors.extend(list(self._get_errors_from_subform(rate_data['name'], rate_form)))
            else:
                rate_instances.append(self._retrieve_feature_rate(rate_form))
        if errors:
            self._errors.setdefault('feature_rates', errors)
        self.new_feature_rates = rate_instances
        rate_ids = lambda x: set([r.id for r in x])
        if (not self.is_update and (self.plan_version is None or
                rate_ids(rate_instances).symmetric_difference(rate_ids(self.plan_version.feature_rates.all())))):
            self.is_update = True
        return original_data

    def clean_product_rates(self):
        original_data = self.cleaned_data['product_rates']
        rates = json.loads(original_data)
        rate_instances = []
        errors = ErrorList()
        for rate_data in rates:
            rate_form = ProductRateForm(rate_data)
            if not rate_form.is_valid():
                errors.extend(list(self._get_errors_from_subform(rate_data['name'], rate_form)))
            else:
                rate_instances.append(self._retrieve_product_rate(rate_form))
        if errors:
            self._errors.setdefault('product_rates', errors)
        self.new_product_rates = rate_instances
        rate_ids = lambda x: set([r.id for r in x])
        if (not self.is_update and (self.plan_version is None or
                rate_ids(rate_instances).symmetric_difference(rate_ids(self.plan_version.product_rates.all())))):
            self.is_update = True
        return original_data

    def save(self, request):
        if not self.is_update:
            messages.info(request, "No changes to rates and roles were present, so the current version was kept.")
            return
        new_version = SoftwarePlanVersion(
            plan=self.plan,
            role=Role.objects.get(id=1), # hacked so it doesn't break - TODO needs to get fixed
        )
        new_version.save()

        for feature_rate in self.new_feature_rates:
            feature_rate.save()
            new_version.feature_rates.add(feature_rate)

        for product_rate in self.new_product_rates:
            product_rate.save()
            new_version.product_rates.add(product_rate)

        new_version.save()


class FeatureRateForm(forms.ModelForm):
    """
    A form for creating a new FeatureRate.
    """
    # feature id will point to a  select2 field, hence the CharField here.
    feature_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    rate_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = FeatureRate
        fields = ['monthly_fee', 'monthly_limit', 'per_excess_fee']

    def __init__(self, data=None, *args, **kwargs):
        super(FeatureRateForm, self).__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.HTML("""
                        <h4><span data-bind="text: name"></span>
                        <span class="label"
                            style="display: inline-block; margin: 0 10px;"
                            data-bind="text: feature_type"></span></h4>
                        <hr />
            """),
            crispy.Field('feature_id', data_bind="value: feature_id"),
            crispy.Field('rate_id', data_bind="value: rate_id"),
            crispy.Field('monthly_fee', data_bind="value: monthly_fee"),
            crispy.Field('monthly_limit', data_bind="value: monthly_limit"),
            crispy.Field('per_excess_fee', data_bind="value: per_excess_fee"),
        )

    def is_new(self):
        return not self['rate_id'].value()

    def get_instance(self, feature):
        instance = self.save(commit=False)
        instance.feature = feature
        return instance


class ProductRateForm(forms.ModelForm):
    """
    A form for creating a new ProductRate.
    """
    # product id will point to a  select2 field, hence the CharField here.
    product_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    rate_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = SoftwareProductRate
        fields = ['monthly_fee']

    def __init__(self, data=None, *args, **kwargs):
        super(ProductRateForm, self).__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.HTML("""
                        <h4><span data-bind="text: name"></span>
                        <span class="label"
                            style="display: inline-block; margin: 0 10px;"
                            data-bind="text: product_type"></span></h4>
                        <hr />
            """),
            crispy.Field('monthly_fee', data_bind="value: monthly_fee"),
        )

    def is_new(self):
        return not self['rate_id'].value()

    def get_instance(self, product):
        instance = self.save(commit=False)
        instance.product = product
        return instance


class RoleForm(forms.ModelForm):
    """
    A form for creating a new ProductRate.
    """
    role_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    # TODO - rate_id ?

    class Meta:
        model = Role
        fields = ['slug', 'name', 'description', 'parameters']

    def __init__(self, data=None, *args, **kwargs):
        super(RoleForm, self).__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.HTML('<h4><span data-bind="text: name"></span></h4>'),
            crispy.Field('parameters', data_bind="value: parameters"),
        )

    def is_new(self):
        return not self['role_id'].value()

    def get_instance(self, role):
        instance = self.save(commit=False)
        instance.role = role
        return instance


class EnterprisePlanContactForm(forms.Form):
    name = forms.CharField(
        label=ugettext_noop("Name")
    )
    company_name = forms.CharField(
        required=False,
        label=ugettext_noop("Company / Organization")
    )
    message = forms.CharField(
        required=False,
        label=ugettext_noop("Message"),
        widget=forms.Textarea
    )

    def __init__(self, domain, web_user, data=None, *args, **kwargs):
        self.domain = domain
        self.web_user = web_user
        super(EnterprisePlanContactForm, self).__init__(data, *args, **kwargs)
        from corehq.apps.domain.views import SelectPlanView
        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.layout = crispy.Layout(
            'name',
            'company_name',
            'message',
            FormActions(
                StrictButton(
                    _("Request Quote"),
                    type="submit",
                    css_class="btn-primary",
                ),
                crispy.HTML('<a href="%(url)s" class="btn">%(title)s</a>' % {
                            'url': reverse(SelectPlanView.urlname, args=[self.domain]),
                            'title': ugettext("Select different plan"),
                }),
            )
        )

    def send_message(self):
        subject = "[Enterprise Plan Request] %s" % self.domain
        context = {
            'name': self.cleaned_data['name'],
            'company': self.cleaned_data['company_name'],
            'message': self.cleaned_data['message'],
            'domain': self.domain,
        }
        html_content = render_to_string('accounting/enterprise_request_email.html', context)
        text_content = """
        Name: %(name)s
        Company: %(company)s
        Domain: %(domain)s
        Message:
        %(message)s
        """ % context
        send_HTML_email(subject, settings.SUPPORT_EMAIL, html_content, text_content,
                        email_from=self.web_user.email)



