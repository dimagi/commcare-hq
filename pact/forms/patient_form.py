import pdb
from django import forms

#from the models, we have this, (couchmodels.py)
#flipping to tuple
from django.core.exceptions import ValidationError
from django.forms import Form
import simplejson
from corehq.apps.api.es import CaseES
from pact.enums import PACT_HP_CHOICES, PACT_DOT_CHOICES, PACT_REGIMEN_CHOICES, GENDER_CHOICES, PACT_RACE_CHOICES, PACT_HIV_CLINIC_CHOICES, PACT_LANGUAGE_CHOICES, CASE_NONART_REGIMEN_PROP, CASE_ART_REGIMEN_PROP, DOT_ART, DOT_NONART
from django.forms import widgets
from pact.regimen import regimen_string_from_doc, regimen_dict_from_choice

def get_hp_choices():
    from pact.reports.patient_list import PactPrimaryHPField
    return [(x['val'], x['text']) for x in PactPrimaryHPField.get_chws()]


class PactPatientForm(Form):
    """
    DocumentForm
    """
    pactid = forms.CharField(label="PACT ID", required=True)

    first_name = forms.CharField(label="First Name", required=True)
    middle_name = forms.CharField(label="Middle Name", required=False)
    last_name = forms.CharField(label="Last Name", required=True)

    gender = forms.ChoiceField(label="Sex", choices=GENDER_CHOICES)
    #source: http://stackoverflow.com/questions/1513502/django-how-to-format-a-datefields-date-representation
    dob = forms.DateField(required=False, label='dob', input_formats=['%m/%d/%Y'], widget=forms.DateInput(format = '%m/%d/%Y', attrs={'class': 'jqui-dtpk'}))
    race = forms.ChoiceField(choices=PACT_RACE_CHOICES)
    preferred_language = forms.ChoiceField(choices=PACT_LANGUAGE_CHOICES)

    mass_health_expiration = forms.DateField(label = "Mass Health expiration date", input_formats=['%m/%d/%Y',''], widget=forms.DateInput(format = '%m/%d/%Y'), required=False)
    ssn = forms.CharField(label="Social Security Number", required=False)

    hp = forms.ChoiceField(label="Primary health promoter", choices=())

    hp_status = forms.ChoiceField(label="HP Status", choices=PACT_HP_CHOICES, required=False)
    dot_status = forms.ChoiceField(label="DOT Status", choices=PACT_DOT_CHOICES, required=False)
    artregimen = forms.ChoiceField(choices=PACT_REGIMEN_CHOICES, required=False)
    nonartregimen = forms.ChoiceField(choices=PACT_REGIMEN_CHOICES, required=False)
    hiv_care_clinic = forms.ChoiceField(choices=PACT_HIV_CLINIC_CHOICES)

    patient_notes = forms.CharField(widget = widgets.Textarea(attrs={'cols':80,'rows':5}), required=False)

    def __init__(self, casedoc, *args, **kwargs):
        super(PactPatientForm, self).__init__(*args, **kwargs)
        self.casedoc = casedoc
        self.fields['hp'].choices = get_hp_choices()
        self.case_es = CaseES()
        for name, field in self.fields.items():
            print "%s: %s" % (name, getattr(self.casedoc, name, ''))

            if name == CASE_ART_REGIMEN_PROP:
                #these really should be a widget of some type
                #dereference the artregimen, dot_a_one...etc to become the comma separated regimen string for the form
                art_regimen_initial = self.casedoc.art_regimen_label_string()
                casedoc_value = art_regimen_initial
            elif name == CASE_NONART_REGIMEN_PROP:
                nonart_regimen_initial = self.casedoc.nonart_regimen_label_string()
                casedoc_value = nonart_regimen_initial
            else:
                casedoc_value = getattr(self.casedoc, name, '')
            field.initial = casedoc_value

    @property
    def clean_changed_data(self):
        #to be called after validation
        ret = {}
        for name, value in self.cleaned_data.items():

            #to verify that the regimens changed calculate the dict of the freq+label ids.
            if name == CASE_ART_REGIMEN_PROP:
                art_props = regimen_dict_from_choice(DOT_ART, value)
                if art_props != self.casedoc.art_properties():
                    ret.update(art_props)
            elif name == CASE_NONART_REGIMEN_PROP:
                nonart_props = regimen_dict_from_choice(DOT_NONART, value)
                if nonart_props != self.casedoc.nonart_properties():
                    ret.update(nonart_props)
            else:
                if getattr(self.casedoc, name, '') != value:
#                    print "%s: %s != %s" % (name, getattr(self.casedoc, name, None), value)
                    ret[name] = value
        return ret

    def clean_dob(self):
        if self.cleaned_data['dob'] is not None:
            return self.cleaned_data['dob'].strftime('%Y-%m-%d')
        else:
            return None

    def clean_mass_health_expiration(self):
        if self.cleaned_data['mass_health_expiration'] is not None:
            return self.cleaned_data['mass_health_expiration'].strftime('%Y-%m-%d')
        else:
            return None


    def clean_pact_id(self):
        if not PactPatient.check_pact_id(self.cleaned_data['pact_id']):
            raise ValidationError("Error, pact id must be unique")
        else:
            return self.cleaned_data['pact_id']

