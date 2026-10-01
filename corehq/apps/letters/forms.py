from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import layout as crispy
from jinja2 import TemplateSyntaxError

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.letters.models import LetterTemplate
from corehq.apps.letters.rendering import validate_template


class LetterTemplateForm(forms.ModelForm):
    class Meta:
        model = LetterTemplate
        fields = ['name', 'body']
        widgets = {'body': forms.Textarea(attrs={'rows': 25, 'class': 'font-monospace'})}
        help_texts = {
            'body': gettext_lazy('HTML with Jinja2 placeholders for case properties, '
                                 'e.g. {{ case_name }} or {{ address }}.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()
        self.helper.layout = crispy.Layout(
            'name',
            'body',
            hqcrispy.FormActions(crispy.Submit('submit', _('Save'))),
        )

    def clean_body(self):
        body = self.cleaned_data['body']
        try:
            validate_template(body)
        except TemplateSyntaxError as e:
            raise forms.ValidationError(
                _('Template error on line {line}: {msg}').format(line=e.lineno, msg=e.message)
            )
        return body
