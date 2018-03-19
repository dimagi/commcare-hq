from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms.layout import Layout, ButtonHolder, Fieldset, Submit
from custom.enikshay.management.commands import (
    data_dumps_person_case,
    data_dumps_adherence_details,
    data_dumps_adherence_summary,
    data_dumps_cbnaat_tests,
    data_dumps_clinical_tests,
    data_dumps_culture_tests,
    data_dumps_dmc_tests,
    data_dumps_drtb_episodes,
    data_dumps_drtb_specific_episodes,
    data_dumps_dst_tests,
    data_dumps_dstb_episodes,
    data_dumps_fllpa_tests,
    data_dumps_other_tests,
    data_dumps_presumptive_episodes,
    data_dumps_referrals,
    data_dumps_sllpa_tests,
)


class ReconciliationTaskForm(forms.Form):
    permitted_tasks = ['duplicate_occurrences_and_episodes_reconciliation',
                       'drug_resistance_reconciliation',
                       'investigations_reconciliation',
                       'multiple_open_referrals_reconciliation']

    email = forms.EmailField(label='Your email')
    commit = forms.BooleanField(label='Commit Changes', required=False)
    person_case_ids = forms.CharField(label='Person Case Ids', required=False,
                                      help_text="Comma separated person case ids to process")
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
                crispy.Field('person_case_ids'),
            ),
            ButtonHolder(
                Submit(
                    "run",
                    "Run",
                    css_class='btn-primary',
                )
            )
        )


class DataDumpTaskForm(forms.Form):
    # all commands to be supported. Just add the command here to add new ones.
    _permitted_tasks = [
        data_dumps_person_case,
        data_dumps_presumptive_episodes,
        data_dumps_dstb_episodes,
        data_dumps_drtb_episodes,
        data_dumps_dmc_tests,
        data_dumps_cbnaat_tests,
        data_dumps_fllpa_tests,
        data_dumps_sllpa_tests,
        data_dumps_culture_tests,
        data_dumps_dst_tests,
        data_dumps_clinical_tests,
        data_dumps_drtb_specific_episodes,
        data_dumps_referrals,
        data_dumps_adherence_summary,
        data_dumps_adherence_details,
        data_dumps_other_tests,
    ]
    permitted_tasks = [choice.__name__.split('.')[-1] for choice in _permitted_tasks]

    email = forms.EmailField(label='Your email or email to send confirmation to')
    full = forms.BooleanField(label='Full Run', required=False)
    task = forms.ChoiceField(label='Task', choices=(
        [('all', 'All')] + [(choice.__name__.split('.')[-1],
                             choice.Command.TASK_NAME.capitalize().replace('_', ' '))
                            for choice in _permitted_tasks]
    ))

    def __init__(self, *args, **kwargs):
        super(DataDumpTaskForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3'
        self.helper.field_class = 'col-sm-5'
        self.helper.layout = Layout(
            Fieldset(
                "Details",
                crispy.Field('email'),
                crispy.Field('full'),
                crispy.Field('task')
            ),
            ButtonHolder(
                Submit(
                    "run",
                    "Run",
                    css_class='btn-primary',
                )
            )
        )
