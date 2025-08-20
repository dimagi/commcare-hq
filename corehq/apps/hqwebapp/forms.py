from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from captcha.fields import ReCaptchaField
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.helper import FormHelper
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm

from corehq.apps.domain.forms import NoAutocompleteMixin
from corehq.apps.users.models import CouchUser
from corehq.util.metrics import metrics_counter

LOCKOUT_MESSAGE = mark_safe(_(  # nosec: no user input
    'Sorry - you have attempted to login with an incorrect password too many times. '
    'Please <a href="/accounts/password_reset_email/">click here</a> to reset your password '
    'or contact the domain administrator.'))


class EmailAuthenticationForm(NoAutocompleteMixin, AuthenticationForm):
    username = forms.EmailField(label=_("Email Address"),
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    if settings.ADD_CAPTCHA_FIELD_TO_FORMS:
        captcha = ReCaptchaField(label="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.ENFORCE_SSO_LOGIN:
            self.fields['username'].widget = forms.TextInput(attrs={
                'class': 'form-control',
                'data-bind': 'textInput: authUsername, onEnterKey: continueOnEnter',
                'placeholder': _("Enter email address"),
            })
            self.fields['password'].widget = forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': _("Enter password"),
            })

    def clean_username(self):
        username = self.cleaned_data.get('username', '').lower()
        return username

    def clean(self):
        username = self.cleaned_data.get('username')
        if username is None:
            raise ValidationError(_('Please enter a valid email address.'))

        password = self.cleaned_data.get('password')
        if not password:
            raise ValidationError(_("Please enter a password."))

        if settings.ADD_CAPTCHA_FIELD_TO_FORMS:
            if not self.cleaned_data.get('captcha'):
                raise ValidationError(_("Please enter valid CAPTCHA"))

        try:
            cleaned_data = super(EmailAuthenticationForm, self).clean()
        except ValidationError:
            user = CouchUser.get_by_username(username)
            if user and user.is_locked_out():
                metrics_counter('commcare.auth.lockouts')
                raise ValidationError(LOCKOUT_MESSAGE)
            else:
                raise
        user = CouchUser.get_by_username(username)
        if user and user.is_locked_out():
            metrics_counter('commcare.auth.lockouts')
            raise ValidationError(LOCKOUT_MESSAGE)
        return cleaned_data


class CloudCareAuthenticationForm(EmailAuthenticationForm):
    username = forms.CharField(label=_("Username"),
                               widget=forms.TextInput(attrs={'class': 'form-control'}))


class BulkUploadForm(forms.Form):
    bulk_upload_file = forms.FileField(label="")
    action = forms.CharField(widget=forms.HiddenInput(), initial='bulk_upload')

    def __init__(self, plural_noun="", action=None, form_id=None, context=None, *args, **kwargs):
        super(BulkUploadForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        if form_id:
            self.helper.form_id = form_id
        self.helper.form_method = 'post'
        if action:
            self.helper.form_action = action
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "",
                *self.crispy_form_fields(context)
            ),
            StrictButton(
                ('<i class="fa-solid fa-cloud-arrow-up"></i> Upload %s' % plural_noun),
                css_class='btn-primary disable-on-submit',
                data_bind='disable: !file()',
                type='submit',
            ),
        )

    def crispy_form_fields(self, context):
        return [
            crispy.Field(
                'bulk_upload_file',
                data_bind="value: file",
            ),
            crispy.Field(
                'action',
            ),
        ]


class AppTranslationsBulkUploadForm(BulkUploadForm):
    language = forms.CharField(widget=forms.HiddenInput)
    validate = forms.BooleanField(label="Just validate and not update translations", required=False,
                                  initial=False)

    def crispy_form_fields(self, context):
        crispy_form_fields = super(AppTranslationsBulkUploadForm, self).crispy_form_fields(context)
        if context.get('can_select_language'):
            crispy_form_fields.extend([
                InlineField('language', data_bind="value: lang")
            ])
        if context.get('can_validate_app_translations'):
            crispy_form_fields.extend([
                crispy.Div(InlineField('validate'))
            ])
        return crispy_form_fields


class HQAuthenticationTokenForm(AuthenticationTokenForm):
    def __init__(self, user, initial_device, request, **kwargs):
        super().__init__(user, initial_device, **kwargs)
        self.request = request

    def clean(self):
        try:
            cleaned_data = super(HQAuthenticationTokenForm, self).clean()
        except ValidationError:
            user_login_failed.send(sender=__name__, credentials={'username': self.user.username},
                request=self.request,
                token_failure=True)
            couch_user = CouchUser.get_by_username(self.user.username)
            if couch_user and couch_user.is_locked_out():
                metrics_counter('commcare.auth.token_lockout')
                raise ValidationError(LOCKOUT_MESSAGE)
            else:
                raise

        # Handle the edge-case where the user enters a correct token
        # after being locked out
        couch_user = CouchUser.get_by_username(self.user.username)
        if couch_user and couch_user.is_locked_out():
            metrics_counter('commcare.auth.lockouts')
            raise ValidationError(LOCKOUT_MESSAGE)
        return cleaned_data


class HQBackupTokenForm(BackupTokenForm):

    def __init__(self, user, initial_device, request, **kwargs):
        super().__init__(user, initial_device, **kwargs)
        self.request = request

    def clean(self):
        try:
            cleaned_data = super(HQBackupTokenForm, self).clean()
        except ValidationError:
            user_login_failed.send(sender=__name__, credentials={'username': self.user.username},
                request=self.request,
                token_failure=True)
            couch_user = CouchUser.get_by_username(self.user.username)
            if couch_user and couch_user.is_locked_out():
                metrics_counter('commcare.auth.token_lockout')
                raise ValidationError(LOCKOUT_MESSAGE)
            else:
                raise

        # Handle the edge-case where the user enters a correct token
        # after being locked out
        couch_user = CouchUser.get_by_username(self.user.username)
        if couch_user and couch_user.is_locked_out():
            metrics_counter('commcare.auth.lockouts')
            raise ValidationError(LOCKOUT_MESSAGE)
        return cleaned_data
