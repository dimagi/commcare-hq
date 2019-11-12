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

class InputStockForm(forms.Form):
    product_id = forms.CharField(widget=forms.HiddenInput())
    product = forms.CharField(widget=forms.HiddenInput(), required=False)
    stock_on_hand = forms.IntegerField(min_value=0, required=False)
    receipts = forms.IntegerField(min_value=0, initial=0, required=False)
    units = forms.CharField(required=False)
    monthly_consumption = forms.DecimalField(required=False, widget=forms.HiddenInput())
    default_consumption = forms.DecimalField(min_value=0, required=False)


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
