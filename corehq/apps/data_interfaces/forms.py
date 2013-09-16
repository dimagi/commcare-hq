from crispy_forms.bootstrap import StrictButton, InlineField
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop


class AddCaseGroupForm(forms.Form):
    name = forms.CharField(required=True, label=ugettext_noop("Group Name"))

    def __init__(self, *args, **kwargs):
        super(AddCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.layout = Layout(
            InlineField('name'),
            StrictButton(
                mark_safe('<i class="icon-plus"></i> %s' % _("Create Group")),
                css_class='btn-success',
                type="submit"
            )
        )
