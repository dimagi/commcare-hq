from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms.layout import Layout, ButtonHolder, Fieldset, Submit


class ReconciliationTaskForm(forms.Form):
    permitted_tasks = ['duplicate_occurrences_and_episodes_reconciliation',
                       'drug_resistance_reconciliation',
                       'investigations_reconciliation',
                       'multiple_open_referrals_reconciliation'
                       ]
    email = forms.EmailField(label='Your email')
    commit = forms.BooleanField(label='Commit Changes', required=False)
    task = forms.ChoiceField(label='Task', choices=(
        [('all', 'All')] + [(choice, choice.capitalize().replace('_', ' ')) for choice in permitted_tasks]
    ))

    def __init__(self, *args, **kwargs):
        super(ReconciliationTaskForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3'
        self.helper.field_class = 'col-sm-5'
        self.helper.layout = Layout(
            Fieldset(
                "Details",
                crispy.Field('email'),
                crispy.Field('commit'),
                crispy.Field('task'),
            ),
            ButtonHolder(
                Submit(
                    "run",
                    "Run",
                    css_class='btn-primary',
                )
            )
        )
