from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import CharField, ModelForm, PasswordInput
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from corehq.apps.consumer_user.models import ConsumerUser


class ChangeContactDetailsForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name']


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
            login_url = reverse(
                'consumer_user:login_with_invitation',
                kwargs={'signed_invitation_id': self.invitation.signature()}
            )
            sign_in_message = _(
                'Username <strong>{email}</strong> is already in use. If you already have an '
                'account, you can sign in <a href="{url}">here</a>').format(email=email, url=login_url)
            raise ValidationError(mark_safe(sign_in_message))

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
            consumer_user = ConsumerUser.objects.create(user=user)
            if self.invitation and not self.invitation.accepted:
                self.invitation.accept_for_consumer_user(consumer_user)
        return user
