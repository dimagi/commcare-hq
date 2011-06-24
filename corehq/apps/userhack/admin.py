from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django import forms
from django.utils.translation import ugettext_lazy as _


class HackedUserChangeForm(UserChangeForm):
    """
    Support > 30 character length usernames in the admin
    """
    username = forms.RegexField(label=_("Username"), max_length=128, regex=r'^[\w.@+-]+$',
        help_text = _("Required. 128 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})

    
class HackedUserAdmin(UserAdmin):
    """
    Support > 30 character length usernames in the admin
    """
    form = HackedUserChangeForm
    
    
admin.site.unregister(User)
admin.site.register(User, HackedUserAdmin)
