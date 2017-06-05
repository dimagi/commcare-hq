from django import forms
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError
from django.contrib.auth import password_validation


class EncodedPasswordChangeFormMixin(object):
    """
    To be used by forms using passwords to enable decoding for obfuscated passwords.
    Expected to be used on classes that override SetPasswordForm.
    It must come before SetPasswordForm in the list of base classes.
    """
    def clean_new_password1(self):
        from corehq.apps.domain.forms import clean_password
        from corehq.apps.hqwebapp.utils import decode_password
        new_password = decode_password(self.cleaned_data.get('new_password1'))
        # User might not be able to submit empty password but decode_password might
        # return empty password in case the password hashing is messed up with
        if new_password == '':
            raise ValidationError(
                _("Password cannot be empty"), code='new_password1_empty',
            )

        return clean_password(new_password)

    def clean_new_password2(self):
        from corehq.apps.hqwebapp.utils import decode_password
        return decode_password(self.cleaned_data.get('new_password2'))

    def clean(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
            )
        password_validation.validate_password(password2, self.user)
        return super(EncodedPasswordChangeFormMixin, self).clean()

