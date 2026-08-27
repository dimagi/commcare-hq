import re
from datetime import timedelta

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from corehq.apps.hqwebapp.fields import TurnstileField
from corehq.apps.public_webforms.models import PublicFormSession


class PublicWebformLinkRequestForm(forms.Form):

    delivery = forms.ChoiceField(
        label=_("How would you like to receive your link?"),
        choices=[],
        widget=forms.RadioSelect,
    )
    email = forms.EmailField(
        label=_("Email Address"),
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': "you@example.com",
            'autocomplete': 'email',
            'x-model': 'email',
        }),
    )
    phone_number = forms.CharField(
        label=_("Phone Number"),
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'type': 'tel',
            'autocomplete': 'tel',
            'x-model': 'phoneNumber',
        }),
    )
    turnstile = TurnstileField()

    def __init__(self, webform, *args, **kwargs):
        self.webform = webform
        super().__init__(*args, **kwargs)
        delivery_choices = []
        if webform.allow_email:
            delivery_choices.append(('email', _("Email")))
        if webform.allow_sms:
            delivery_choices.append(('sms', _("Text Message")))

        self.fields['delivery'].choices = delivery_choices
        self.fields['delivery'].initial = delivery_choices[0][0] if delivery_choices else None

    @property
    def can_choose_delivery(self):
        return len(self.fields['delivery'].choices) > 1

    def clean(self):
        cleaned_data = super().clean()
        delivery = cleaned_data.get('delivery')
        # the field for the option not chosen is submitted but ignored, so
        # switching between them can't leave a stale value behind
        if delivery == 'email':
            cleaned_data['phone_number'] = ''
            if not cleaned_data.get('email'):
                self.add_error('email', _("Enter the email address to send your link to."))
        elif delivery == 'sms':
            cleaned_data['email'] = ''
            cleaned_data['phone_number'] = self._clean_phone_number(
                cleaned_data.get('phone_number'))
        return cleaned_data

    def _clean_phone_number(self, phone_number):
        # the widget submits a full international number, punctuation and all
        digits = re.sub(r'[\s+\-().]', '', phone_number or '')
        if not digits:
            self.add_error(
                'phone_number', _("Enter the phone number to send your link to."))
        elif not digits.isdigit():
            self.add_error('phone_number', _("Enter a valid phone number."))
        return digits

    def create_session(self):
        return PublicFormSession.objects.create(
            public_webform=self.webform,
            email=self.cleaned_data['email'],
            phone_number=self.cleaned_data['phone_number'],
            expires_at=timezone.now() + timedelta(hours=1),
        )
