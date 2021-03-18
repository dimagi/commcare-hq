from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import CharField, ModelForm, PasswordInput
from django.utils.translation import ugettext_lazy as _

from corehq.apps.consumer_user.const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_ERROR,
    CONSUMER_INVITATION_STATUS,
)
from corehq.apps.consumer_user.models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
)
from corehq.apps.hqcase.utils import update_case


class ConsumerUserSignUpForm(ModelForm):

    email = CharField(required=True)

    def __init__(self, *args, **kwargs):
        self.invitation = kwargs.pop('invitation', None)
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Email Address'
        for key in self.fields:
            self.fields[key].required = True

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']
        widgets = {
            'password': PasswordInput(),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if (
            User.objects.filter(username=email).exists()
            or ConsumerUser.objects.filter(user__username=email).exists()
        ):
            raise ValidationError(_(u'Username "{username}" is already in use.'), params={"username": email})

        return email

    def save(self, commit=True):
        user = super(ConsumerUserSignUpForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
            consumer_user = ConsumerUser.objects.create(user=user)
            if self.invitation:
                self.invitation.accepted = True
                self.invitation.save()
                ConsumerUserCaseRelationship.objects.create(
                    case_id=self.invitation.demographic_case_id,
                    domain=self.invitation.domain,
                    consumer_user=consumer_user
                )
                update_case(
                    self.invitation.domain, self.invitation.case_id,
                    {
                        CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_ACCEPTED,
                        CONSUMER_INVITATION_ERROR: "",
                    }
                )
        return user
