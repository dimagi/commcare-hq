from corehq.apps.reminders.forms import BroadcastForm
from corehq.apps.reminders.models import (RECIPIENT_USER_GROUP,
    RECIPIENT_LOCATION)
from crispy_forms import layout as crispy
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy

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
    monthly_consumption = forms.IntegerField(required=False, widget=forms.HiddenInput())


class EWSBroadcastForm(BroadcastForm):
    role = forms.ChoiceField(
        required=False,
        label=ugettext_lazy('Send to users with role'),
        choices=((role, ugettext_lazy(role)) for role in EWS_USER_ROLES),
    )

    @property
    def crispy_recipient_fields(self):
        fields = super(EWSBroadcastForm, self).crispy_recipient_fields
        fields.append(
            crispy.Div(
                crispy.Field(
                    'role',
                    data_bind='value: role',
                ),
                data_bind='visible: showUserGroupSelect() || showLocationSelect()',
            )
        )
        return fields

    def clean_role(self):
        if self.cleaned_data.get('recipient_type') not in (RECIPIENT_USER_GROUP,
                RECIPIENT_LOCATION):
            return None

        value = self.cleaned_data.get('role')
        if value not in EWS_USER_ROLES:
            raise ValidationError(_('Invalid choice selected.'))
        return value

    def get_user_data_filter(self):
        role = self.cleaned_data.get('role')
        if role is None or role == ROLE_ALL:
            return {}
        else:
            return {'role': [role]}
