from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy
from corehq.apps.domain.forms import clean_password
from corehq.apps.users.models import CouchUser

from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe

from datetime import datetime


class HQPasswordChangeForm(PasswordChangeForm):

    new_password1 = forms.CharField(label=_("New password"),
                                    widget=forms.PasswordInput(),
                                    help_text=mark_safe("""
                                    <span data-bind="text: passwordHelp, css: color">
                                    """))

    def __init__(self, user, *args, **kwargs):

        super(HQPasswordChangeForm, self).__init__(user, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Specify New Password'),
                'old_password',
                crispy.Field('new_password1', data_bind="value: password, valueUpdate: 'input'"),
                'new_password2'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Change Password'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )

    def clean_new_password1(self):
        return clean_password(self.cleaned_data.get('new_password1'))

    def save(self, commit=True):
        user = super(HQPasswordChangeForm, self).save(commit)
        couch_user = CouchUser.from_django_user(user)
        couch_user.last_password_set = datetime.utcnow()
        if commit:
            couch_user.save()
        return user
