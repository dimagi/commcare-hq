from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from django import forms

from corehq.apps.hqwebapp import crispy as hqcrispy


class ChooseFruitForm(forms.Form):
    fruit = forms.ChoiceField(
        label='Favorite fruit',
        choices=(
            ('apple', 'Apple'),
            ('banana', 'Banana'),
            ('orange', 'Orange'),
        ),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Field(
                'fruit',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    'Next',
                    type='submit',
                    css_class='btn btn-primary',
                ),
                css_class='mb-0',
            ),
        )

    def clean_fruit(self):
        fruit = self.cleaned_data.get('fruit')
        if not fruit:
            raise forms.ValidationError('Please choose a fruit to continue.')
        return fruit


class ConfirmFruitChoiceForm(forms.Form):
    fruit = forms.CharField(
        widget=forms.HiddenInput,
        required=False,
    )
    next_step = forms.ChoiceField(
        label='What would you like to do?',
        required=False,
        widget=forms.RadioSelect,
        choices=(
            ('confirm', 'Yes, save this choice.'),
            ('change', 'No, go back and change it.'),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            'fruit',
            crispy.Field(
                'next_step',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    'Next',
                    type='submit',
                    css_class='btn btn-primary',
                ),
                css_class='mb-0',
            ),
        )

    def clean_fruit(self):
        fruit = self.cleaned_data.get('fruit')
        if not fruit:
            raise forms.ValidationError('Missing fruit choice. Please go back and choose again.')
        return fruit

    def clean_next_step(self):
        next_step = self.cleaned_data.get('next_step')
        if not next_step:
            raise forms.ValidationError('Please choose an option to continue.')
        return next_step
