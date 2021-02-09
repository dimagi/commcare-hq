from django.forms import ModelForm
from django.forms import PasswordInput
from django.contrib.auth.models import User


class PatientSignUpForm(ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']
        widgets = {
            'password': PasswordInput(),
        }

    def save(self, commit=True):
        user = super(PatientSignUpForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
