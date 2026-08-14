from django import forms
from django.utils.translation import gettext_lazy as _


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
        }),
    )

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
