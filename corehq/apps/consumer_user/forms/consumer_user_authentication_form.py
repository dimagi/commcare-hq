from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from corehq.apps.consumer_user.const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_STATUS,
)
from corehq.apps.consumer_user.models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
)
from corehq.apps.domain.forms import NoAutocompleteMixin
from corehq.apps.hqcase.utils import update_case


class ConsumerUserAuthenticationForm(NoAutocompleteMixin, AuthenticationForm):
    username = forms.EmailField(label=_("Email Address"),
                                widget=forms.TextInput(attrs={'class': 'form-control'}),
                                required=True)
    password = forms.CharField(label=_("Password"),
                               widget=forms.PasswordInput(attrs={'class': 'form-control'}),
                               required=True)

    def __init__(self, *args, **kwargs):
        self.invitation = kwargs.pop('invitation', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        username = self.cleaned_data.get('username')
        if username is None:
            raise ValidationError(_('Please enter a valid email address.'))

        password = self.cleaned_data.get('password')
        if not password:
            raise ValidationError(_("Please enter a password."))
        cleaned_data = super(ConsumerUserAuthenticationForm, self).clean()
        consumer_user = ConsumerUser.objects.get_or_create(user=self.user_cache)
        if self.invitation and not self.invitation.accepted:
            self.invitation.accept()
            ConsumerUserCaseRelationship.objects.create(
                case_id=self.invitation.demographic_case_id,
                domain=self.invitation.domain,
                consumer_user=consumer_user[0]
            )
            update_case(
                self.invitation.domain, self.invitation.case_id,
                {CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_ACCEPTED}
            )
        return cleaned_data
