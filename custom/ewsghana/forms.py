from django.core.urlresolvers import reverse
from django.template import Context
from django.template.loader import get_template
from corehq.apps.reminders.forms import BroadcastForm
from corehq.apps.reminders.models import (RECIPIENT_USER_GROUP,
    RECIPIENT_LOCATION)
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


class FacilitiesSelectWidget(forms.Widget):
    def __init__(self, attrs=None, domain=None, id='supply-point', multiselect=False):
        super(FacilitiesSelectWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id
        self.multiselect = multiselect

    def render(self, name, value, attrs=None):
        return get_template('locations/manage/partials/autocomplete_select_widget.html').render(Context({
            'id': self.id,
            'name': name,
            'value': value or '',
            'query_url': reverse('custom.ewsghana.views.non_administrative_locations_for_select2',
                                 args=[self.domain]),
            'multiselect': self.multiselect,
        }))


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
        self.fields['facility'].widget = FacilitiesSelectWidget(domain=domain, id='facility')

    def save(self, user, domain):
        ews_extension = EWSExtension.objects.get_or_create(user_id=user.get_id, domain=domain)[0]
        ews_extension.domain = domain
        ews_extension.location_id = self.cleaned_data['facility']
        ews_extension.sms_notifications = self.cleaned_data['sms_notifications']
        ews_extension.save()
