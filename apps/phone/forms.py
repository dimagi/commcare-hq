from django import forms 
from django.contrib.auth.models import User

from corehq.apps.domain.forms import DomainBoundModelChoiceField

class UserForm(forms.ModelForm):
    """
    A super-lightweight user creation form.
    """
    # We use a django ModelForm to get the username uniqueness 
    # validation for free.
    
    # the password field is represented as plaintext for now
    # because the system auto-generates these, but allows them 
    # to be edited.
    password = forms.CharField(max_length=128, required=True,
                               help_text="The user's password")

    class Meta:
        model = User
        fields = ("username", "password")


class UserSelectionForm(forms.Form):
    
    user = DomainBoundModelChoiceField(queryset=User.objects.none())
    
    def __init__(self, domain=None, *args, **kwargs):
        super(UserSelectionForm, self).__init__(*args, **kwargs)
        # Here's how we set the runtime filtering of the users to be displayed 
        # in the selector box
        if domain is not None:
            self.fields['user'].domain = domain

    
    class Meta:
        model = User
        fields = ("username", "password")


