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
        initial_criteria = []
        # self.fields['user_data_criteria'] = forms.JSONField(
        #     required=False,
        #     widget=forms.HiddenInput(attrs={'id': 'user-data-criteria-json'})
        # )

        if self.instance and self.instance.user_data_criteria:
            print("self.instance.user_data_criteria", self.instance.user_data_criteria)
            initial_criteria = [
                {'operator': criteria['operator'], 'property_name': criteria['property_name']}
                for criteria in self.instance.user_data_criteria
            ]

        # Create individual criteria forms for the template to render
        self.criteria_forms = []
        print("initial_criteria", initial_criteria)
        if initial_criteria:
            for criteria in initial_criteria:
                print("criteria", criteria)
                form = UserDataCriteriaForm(initial=criteria)
                self.criteria_forms.append(form)
        else:
            # Add one empty form by default
            self.criteria_forms.append(UserDataCriteriaForm())

    def clean(self):
        cleaned_data = super().clean()
        user_data_criteria = cleaned_data.get('user_data_criteria')
        print("user_data_criteria", user_data_criteria)
        if user_data_criteria is None:
            cleaned_data['user_data_criteria'] = []

        return cleaned_data

    def get_context(self):
        context = super().get_context()
        context.update({
            'criteria_forms': self.criteria_forms,
            'empty_criteria_form': UserDataCriteriaForm(),  # For JavaScript to clone
        })
        return context

    def save(self, commit=True):
        criteria_data = []
        for form in self.criteria_forms:
            if form.is_valid():
                print("in form is valid")
                operator = form.cleaned_data.get('operator')
                print("operator", operator)
                property_name = form.cleaned_data.get('property_name')
                print("property_name", property_name)
                if operator and property_name:
                    criteria_data.append([operator, property_name])
        print("criteria_data", criteria_data)

        # Save the user_data_criteria to the instance
        self.instance.domain = self.domain
        return super().save(commit)

