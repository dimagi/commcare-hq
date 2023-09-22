import re

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
        required=True
    )

    from_email = forms.EmailField(
        label=_("Sender's email"),
        required=True,
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
        label=_("SNS endpoint secret"),
        required=False,
        help_text=_("Applicable only when gateway is Amazon's SES and "
                    "tracking headers are enabled. This secret "
                    "is used in the AWS SNS settings.")
    )

    class Meta:
        model = EmailSettings
        fields = [
            'username',
            'plaintext_password',
            'server',
            'port',
            'from_email',
            'use_this_gateway',
            'use_tracking_headers',
            'sns_secret'
        ]

    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            # `plaintext_password` is not a database field, and so
            # super().__init__() will not update `initial` with it. We
            # need to do that here.
            #
            # We use PASSWORD_PLACEHOLDER to avoid telling the user what
            # the password is, but still indicating that it has been
            # set. (The password is only changed if its value is not
            # PASSWORD_PLACEHOLDER.)
            password = kwargs['instance'].plaintext_password
            if 'initial' in kwargs:
                kwargs['initial'].update({
                    'plaintext_password': PASSWORD_PLACEHOLDER if password else '',
                })
            else:
                kwargs['initial'] = {
                    'plaintext_password': PASSWORD_PLACEHOLDER if password else '',
                }
        super().__init__(*args, **kwargs)

    @cached_property
    def helper(self):
        helper = hqcrispy.HQFormHelper()
        helper.layout = crispy.Layout(
            twbscrispy.PrependedText('use_this_gateway', ''),
            crispy.Field('username'),
            crispy.Field('plaintext_password'),
            crispy.Field('server'),
            crispy.Field('port'),
            crispy.Field('from_email'),
            twbscrispy.PrependedText('use_tracking_headers', ''),
            crispy.Field('sns_secret'),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
            )
        )
        return helper

    def clean_port(self):
        port = self.cleaned_data.get('port')
        if port is None:
            raise forms.ValidationError("Port is a mandatory field.")
        if port is not None and (port < 1 or port > 65535):
            raise forms.ValidationError("Port must be a valid integer between 1 and 65535.")
        return port

    def clean_from_email(self):
        from_email = self.cleaned_data.get('from_email')
        if not from_email:
            raise forms.ValidationError("Sender's email address is a mandatory field.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", from_email):
            raise forms.ValidationError("Enter a valid email address.")
        return from_email

    def clean_server(self):
        server = self.cleaned_data.get('server')
        if not server:
            raise forms.ValidationError("Server is a mandatory field.")
        # Validate that the server follows the format smtp.example.com
        if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', server):
            raise forms.ValidationError("Server should be in the format 'smtp.example.com'.")
        return server

    def save(self, commit=True):
        self.instance.plaintext_password = self.cleaned_data['plaintext_password']
        return super().save(commit)
