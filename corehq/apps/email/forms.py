from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from django import forms
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from corehq.apps.email.models import EmailSettings
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.motech.const import PASSWORD_PLACEHOLDER


class EmailSMTPSettingsForm(forms.ModelForm):
    username = forms.CharField(required=True)

    plaintext_password = forms.CharField(
        label=_("Password"),
        required=True,
        widget=forms.PasswordInput(render_value=True),
    )

    server = forms.CharField(
        label=_('Server'),
        required=True,
        help_text=_('e.g. "smtp.example.com"'),
    )

    port = forms.IntegerField(
        label=_("Port"),
        required=True,
        min_value=1,
        max_value=65535,
    )

    from_email = forms.EmailField(
        label=_("Sender's Email"),
        required=True,
    )

    return_path_email = forms.EmailField(
        label=_("Return Path Email"),
        required=False,
        help_text=_("The email address to which message bounces and complaints should be sent")
    )

    use_this_gateway = forms.BooleanField(
        label=_("Use Gateway?"),
        required=False,
        help_text=_("Select this option to use this email gateway for sending emails")
    )

    use_tracking_headers = forms.BooleanField(
        label=_("Use Tracking Headers"),
        required=False,
        help_text=_("Applicable for Amazon's gateway. When selected, "
                    "emails will be sent with tracking headers along with other headers.")
    )

    sns_secret = forms.CharField(
        label=_("SNS Endpoint Secret"),
        required=False,
        disabled=True,
        help_text=_("Applicable only when gateway is Amazon's SES and "
                    "tracking headers are enabled. This secret "
                    "is used in the AWS SNS settings.")
    )

    ses_config_set_name = forms.CharField(
        label=_("SES Configuration Set Name"),
        required=False,
        help_text=_("Applicable only when gateway is Amazon's SES and "
                    "tracking headers are enabled.")
    )

    class Meta:
        model = EmailSettings
        fields = [
            'username',
            'plaintext_password',
            'server',
            'port',
            'from_email',
            'return_path_email',
            'use_this_gateway',
            'use_tracking_headers',
            'sns_secret',
            'ses_config_set_name',
        ]

    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            # `plaintext_password` is not a database field, so we
            # need to update it in 'initial' here.
            password = kwargs['instance'].plaintext_password
            kwargs.setdefault('initial', {})
            kwargs['initial'].update({'plaintext_password': PASSWORD_PLACEHOLDER if password else ''})
        super().__init__(*args, **kwargs)

    @cached_property
    def helper(self):
        helper = hqcrispy.HQFormHelper()
        helper.form_id = "email_settings_form"
        helper.layout = crispy.Layout(
            twbscrispy.PrependedText('use_this_gateway', ''),
            crispy.Field('username'),
            crispy.Field('plaintext_password'),
            crispy.Field('server'),
            crispy.Field('port'),
            crispy.Field('from_email'),
            crispy.Field('return_path_email'),
            twbscrispy.PrependedText('use_tracking_headers', ''),
            crispy.Field('sns_secret'),
            crispy.Field('ses_config_set_name'),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Saved"),
                    type="submit",
                    css_class="btn-primary disable-on-submit",
                    data_bind="text: buttonText, enable: isFormChanged",
                ),
            )
        )
        return helper

    def save(self, commit=True):
        self.instance.plaintext_password = self.cleaned_data['plaintext_password']
        return super().save(commit)
