from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import PrependedText, StrictButton
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy


class EnterpriseSettingsForm(forms.Form):
    restrict_domain_creation = forms.BooleanField(
        label=ugettext_lazy("Restrict Project Space Creation"),
        required=False,
        help_text=ugettext_lazy("Do not allow current web users, other than enterprise admins, "
                                "to create new project spaces."),
    )
    restrict_signup = forms.BooleanField(
        label=ugettext_lazy("Restrict User Signups"),
        required=False,
        help_text=ugettext_lazy("<span data-bind='html: restrictSignupHelp'></span>"),
    )
    restrict_signup_message = forms.CharField(
        label="Signup Restriction Message",
        required=False,
        help_text=ugettext_lazy("Message to display to users who attempt to sign up for an account"),
        widget=forms.Textarea(attrs={'rows': 2, 'maxlength': 512}),
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain', None)
        self.account = kwargs.pop('account', None)
        kwargs['initial'] = {
            "restrict_domain_creation": self.account.restrict_domain_creation,
            "restrict_signup": self.account.restrict_signup,
            "restrict_signup_message": self.account.restrict_signup_message,
        }
        super(EnterpriseSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = 'enterprise-settings-form'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = reverse("edit_enterprise_settings", args=[self.domain])
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Edit Enterprise Settings"),
                PrependedText('restrict_domain_creation', ''),
                crispy.Div(
                    PrependedText('restrict_signup', '', data_bind='checked: restrictSignup'),
                ),
                crispy.Div(
                    crispy.Field('restrict_signup_message'),
                    data_bind='visible: restrictSignup',
                ),
            )
        )
        self.helper.layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Enterprise Settings"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )

    def clean_restrict_signup_message(self):
        message = self.cleaned_data['restrict_signup_message']
        if self.cleaned_data['restrict_signup'] and not message:
            raise ValidationError(_("If restricting signups, a message is required."))
        return message

    def save(self, account):
        account.restrict_domain_creation = self.cleaned_data.get('restrict_domain_creation', False)
        account.restrict_signup = self.cleaned_data.get('restrict_signup', False)
        account.restrict_signup_message = self.cleaned_data.get('restrict_signup_message', '')
        account.save()
        return True
