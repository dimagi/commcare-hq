from __future__ import absolute_import
from __future__ import unicode_literals

from django import forms
from django.utils.translation import (
    ugettext as _,
)
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from crispy_forms import layout as crispy

from corehq.motech.utils import (
    b64_aes_decrypt,
    b64_aes_encrypt,
)
from custom.icds.models import (
    CCZHostingLink,
)


class CCZHostingLinkForm(forms.ModelForm):
    class Meta:
        model = CCZHostingLink
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(CCZHostingLinkForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        save_button_text = _('Update') if self.instance.pk else _('Create')
        self.helper.layout.append(Submit('save', save_button_text))
        self.helper.layout = crispy.Fieldset(_("CCZ Hosting Link"), self.helper.layout)
        self.fields['identifier'].widget.attrs.update({'class': 'text-lowercase'})
        self.initial['password'] = b64_aes_decrypt(self.instance.password)

    def clean_password(self):
        return b64_aes_encrypt(self.cleaned_data['password'])
