from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse
from corehq.apps.locations.forms import LocationSelectWidget
from corehq.messaging.scheduling.forms import BroadcastForm as NewRemindersBroadcastForm
from crispy_forms import layout as crispy
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from custom.ewsghana.models import EWSExtension

ROLE_ALL = '(any role)'
ROLE_IN_CHARGE = 'In Charge'
ROLE_NURSE = 'Nurse'
ROLE_PHARMACIST = 'Pharmacist'
ROLE_LABORATORY_STAFF = 'Laboratory Staff'
ROLE_OTHER = 'Other'
ROLE_FACILITY_MANAGER = 'Facility Manager'

EWS_USER_ROLES = (
    ROLE_ALL,
    ROLE_IN_CHARGE,
    ROLE_NURSE,
    ROLE_PHARMACIST,
    ROLE_LABORATORY_STAFF,
    ROLE_OTHER,
    ROLE_FACILITY_MANAGER,
)


class InputStockForm(forms.Form):
    product_id = forms.CharField(widget=forms.HiddenInput())
    product = forms.CharField(widget=forms.HiddenInput(), required=False)
    stock_on_hand = forms.IntegerField(min_value=0, required=False)
    receipts = forms.IntegerField(min_value=0, initial=0, required=False)
    units = forms.CharField(required=False)
    monthly_consumption = forms.DecimalField(required=False, widget=forms.HiddenInput())
    default_consumption = forms.DecimalField(min_value=0, required=False)


class NewRemindersEWSBroadcastForm(NewRemindersBroadcastForm):
    use_advanced_user_data_filter = False

    ews_user_role = forms.ChoiceField(
        required=True,
        label=ugettext_lazy("Send to users with role"),
        choices=((role, ugettext_lazy(role)) for role in EWS_USER_ROLES),
    )

    def get_recipients_layout_fields(self):
        fields = super(NewRemindersEWSBroadcastForm, self).get_recipients_layout_fields()
        fields.append(
            crispy.Div(
                crispy.Field('ews_user_role'),
            )
        )
        return fields

    def distill_user_data_filter(self):
        role = self.cleaned_data['ews_user_role']
        if role == ROLE_ALL:
            return {}

        return {'role': [role]}

    def clean_use_user_data_filter(self):
        return None

    def clean_user_data_property_name(self):
        return None

    def clean_user_data_property_value(self):
        return None

    def compute_initial(self):
        result = super(NewRemindersEWSBroadcastForm, self).compute_initial()
        if self.initial_schedule:
            if (
                self.initial_schedule.user_data_filter and
                len(self.initial_schedule.user_data_filter.get('role', [])) == 1
            ):
                result['ews_user_role'] = self.initial_schedule.user_data_filter['role'][0]

        return result


class EWSUserSettings(forms.Form):
    facility = forms.CharField(required=False)
    sms_notifications = forms.BooleanField(required=False, label='Needs SMS notifications')

    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        domain = None
        if 'domain' in kwargs:
            domain = kwargs['domain']
            del kwargs['domain']
        super(EWSUserSettings, self).__init__(*args, **kwargs)
        query_url = reverse('non_administrative_locations_for_select2', args=[domain])
        self.fields['facility'].widget = LocationSelectWidget(domain=domain, id='facility', query_url=query_url)

    def save(self, user, domain):
        ews_extension = EWSExtension.objects.get_or_create(user_id=user.get_id, domain=domain)[0]
        ews_extension.domain = domain
        ews_extension.location_id = self.cleaned_data['facility']
        ews_extension.sms_notifications = self.cleaned_data['sms_notifications']
        ews_extension.save()
