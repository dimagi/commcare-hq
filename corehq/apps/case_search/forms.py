from django import forms

from .models import CSQLFixtureExpression


class CSQLFixtureExpressionForm(forms.ModelForm):
    template_name = 'case_search/csql_expression_form.html'

    class Meta:
        model = CSQLFixtureExpression
        fields = ["name", "csql"]
        widgets = {
            'csql': forms.Textarea(),
        }

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.fields['name'].widget.attrs = {
            'placeholder': "name",
            'class': "form-control",
            'maxlength': "64",
        }
        self.fields['csql'].widget.attrs = {
            'placeholder': "@status = 'open'",
            'class': "form-control vertical-resize",
            'spellcheck': "false",
        }

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)
