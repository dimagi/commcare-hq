from __future__ import absolute_import
from __future__ import unicode_literals

from django import forms
from corehq.motech.utils import b64_aes_decrypt


class CCZHostingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(CCZHostingForm, self).__init__(*args, **kwargs)
        self.initial['password'] = b64_aes_decrypt(self.instance.password)
