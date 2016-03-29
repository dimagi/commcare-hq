from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy

from corehq.apps.analytics.models import ABType, HubspotAB, FeatureAB

class NewABForm(forms.Form):

    ab_type = forms.ChoiceField(
        label="AB Type",
        choices=ABType.CHOICES,
        required=True
    )

    partition = forms.FloatField(
        required=True,
        min_value=0.0,
        max_value=1.0
    )

    slug = forms.CharField(
        required=True,
        max_length=80
    )

    description = forms.CharField(
        required=False,
        max_length=128
    )

    def __init__(self, *args, **kwargs):

        super(NewABForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'ab_type',
                'partition',
                'slug',
                'description',
                'immediate'
            ),
            hqcrispy.FormActions(
                crispy.HTML('<a href={% url "ab_test_list" %} class="btn btn-danger">Return to list</a>'),
                twbscrispy.StrictButton(
                    'Submit',
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )

    def create_new_ab_test(self):
        ab_type = self.cleaned_data['ab_type']
        partition = self.cleaned_data['partition']
        slug = self.cleaned_data['slug']
        description = self.cleaned_data['description']
        if ab_type == ABType.HUBSPOT:
            ab = HubspotAB(partition=partition, slug=slug, description=description)
            ab.save()
            ab.update_all_users()
