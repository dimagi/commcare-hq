from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from auditcare.signals import user_login_failed
from django import forms


class SignaledAuthenticationForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                user_login_failed.send(sender=self, request=self.request, username=username) # This is new
                raise forms.ValidationError(_("Please enter a correct username and password. Note that both fields are case-sensitive."))
            elif not self.user_cache.is_active:
                raise forms.ValidationError(_("This account is inactive."))
        return self.cleaned_data

