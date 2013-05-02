from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django import forms
from django.utils.translation import ugettext_lazy as _
from django_digest.models import UserNonce, PartialDigest


class HackedUserChangeForm(UserChangeForm):
    """
    Support > 30 character length usernames in the admin
    """
    username = forms.RegexField(label=_("Username"), max_length=128, regex=r'^[\w.@+-]+$',
        help_text = _("Required. 128 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})

    def _get_validation_exclusions(self):
        # this is super, super dirty. Don't tell anyone.
        exclusions = super(HackedUserChangeForm, self)._get_validation_exclusions()
        exclusions.append("username")
        return exclusions

class HackedUserAdmin(UserAdmin):
    """
    Support > 30 character length usernames in the admin
    """
    form = HackedUserChangeForm
    
    
admin.site.unregister(User)
admin.site.register(User, HackedUserAdmin)

class DDUserNonceAdmin(admin.ModelAdmin):
    list_display = ('user', 'nonce', 'count', 'last_used_at')

class DDPartialDigestAdmin(admin.ModelAdmin):
    list_display = ('user', 'partial_digest', 'confirmed')
    search_fields = ('login',)

admin.site.register(UserNonce, DDUserNonceAdmin)
admin.site.register(PartialDigest, DDPartialDigestAdmin)