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

    def get_context(self):
        context = super().get_context()
        context.update({
            'filter_modal_form': CSQLFixtureFilterForm(instance=self.instance),
        })
        return context

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)


class UserDataCriteriaForm(forms.Form):
    operator = forms.ChoiceField(
        choices=[
            (CSQLFixtureExpression.MATCH_IS, 'IS'),
            (CSQLFixtureExpression.MATCH_IS_NOT, 'IS NOT'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control user-data-operator',
            'style': 'display: inline-block; width: auto; margin-right: 10px;'
        })
    )
    property_name = forms.CharField(
        max_length=128,
        widget=forms.TextInput(attrs={
            'class': 'form-control user-data-property',
            'placeholder': 'property_name',
            'style': 'display: inline-block; width: auto;'
        })
    )


class CSQLFixtureFilterForm(forms.ModelForm):
    template_name = 'case_search/csql_modal_form.html'

    class Meta:
        model = CSQLFixtureExpression
        fields = ["user_data_criteria"]

    def get_context(self):
        context = super().get_context()
        context.update({
            'criteria_forms': self._get_criteria_forms(),
        })
        return context

    def _get_criteria_forms(self):
        if not self.instance or not self.instance.user_data_criteria:
            return []

        return [
            UserDataCriteriaForm(initial={
                'operator': criteria['operator'],
                'property_name': criteria['property_name']
            })
            for criteria in self.instance.user_data_criteria
        ]
