from django.contrib.auth.models import User
from django.forms import ModelForm


class ChangeContactDetailsForm(ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name']

    def save(self, commit=True):
        user = super(ChangeContactDetailsForm, self).save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user
