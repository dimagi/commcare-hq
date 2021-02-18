from django.forms import ModelForm
from django.forms import PasswordInput
from django.contrib.auth.models import User
from corehq.apps.consumer_user.models import ConsumerUser
from corehq.apps.consumer_user.models import ConsumerUserCaseRelationship
from corehq.apps.consumer_user.utils import hash_username_from_email


class PatientSignUpForm(ModelForm):

    def __init__(self, *args, **kwargs):
        self.invitation = kwargs.pop('invitation', None)
        super().__init__(*args, **kwargs)
        for key in self.fields:
            self.fields[key].required = True

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']
        widgets = {
            'password': PasswordInput(),
        }

    def save(self, commit=True):
        user = super(PatientSignUpForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.username = hash_username_from_email(self.cleaned_data['email'])
        if commit:
            user.save()
            consumer_user = ConsumerUser.objects.create(user=user)
            if self.invitation:
                self.invitation.accepted = True
                self.invitation.save()
            _ = ConsumerUserCaseRelationship.objects.create(case_id=self.invitation.case_id,
                                                            domain=self.invitation.domain,
                                                            case_user_id=consumer_user.id)
        return user
