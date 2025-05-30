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
            'filter_modal_form': CSQLFixtureFilterForm(self.domain, instance=self.instance),
        })
        return context

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)


class UserDataCriteriaForm(forms.Form):
    """Form for individual user data criteria pairs"""
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
        max_length=100,
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

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        print("args", args)
        print("kwargs", kwargs)

    def clean(self):
        cleaned_data = super().clean()
        user_data_criteria = cleaned_data.get('user_data_criteria')
        print("user_data_criteria", user_data_criteria)
        if user_data_criteria is None:
            cleaned_data['user_data_criteria'] = []

        return cleaned_data

    def get_context(self):
        initial_criteria = []
        if self.instance and self.instance.user_data_criteria:
            print("self.instance.user_data_criteria", self.instance.user_data_criteria)
            initial_criteria = [
                {'operator': criteria['operator'], 'property_name': criteria['property_name']}
                for criteria in self.instance.user_data_criteria
            ]
        criteria_forms = []
        if initial_criteria:
            for criteria in initial_criteria:
                print("criteria", criteria)
                form = UserDataCriteriaForm(initial=criteria)
                criteria_forms.append(form)
        else:
            # Add one empty form by default
            criteria_forms.append(UserDataCriteriaForm())
        print("get_context", criteria_forms)
        context = super().get_context()
        context.update({
            'criteria_forms': criteria_forms,
        })
        return context

    def save(self, commit=True):      # Save the user_data_criteria to the instance
        self.instance.domain = self.domain
        return super().save(commit)

