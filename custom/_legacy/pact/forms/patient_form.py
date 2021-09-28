from django import forms

#from the models, we have this, (couchmodels.py)
#flipping to tuple
from django.forms import Form
from corehq.apps.api.es import ReportCaseESView
from dimagi.utils.parsing import json_format_date
from pact.enums import PACT_HP_CHOICES, PACT_DOT_CHOICES, PACT_REGIMEN_CHOICES, GENDER_CHOICES, PACT_RACE_CHOICES, PACT_HIV_CLINIC_CHOICES, PACT_LANGUAGE_CHOICES, CASE_NONART_REGIMEN_PROP, CASE_ART_REGIMEN_PROP, DOT_ART, DOT_NONART
from django.forms import widgets
from pact.regimen import regimen_dict_from_choice


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
    dob = forms.DateField(required=False, label='DOB (m/d/y)', input_formats=['%m/%d/%Y'], widget=forms.DateInput(format = '%m/%d/%Y', attrs={'class': 'jqui-dtpk'}))
    race = forms.ChoiceField(choices=PACT_RACE_CHOICES)
    preferred_language = forms.ChoiceField(choices=PACT_LANGUAGE_CHOICES)

    mass_health_expiration = forms.DateField(label = "Mass Health expiration date (m/d/y)", input_formats=['%m/%d/%Y', ''], widget=forms.DateInput(format = '%m/%d/%Y'), required=False)
    ssn = forms.CharField(label="Social Security Number", required=False)

    hp = forms.ChoiceField(label="Primary health promoter", choices=())

    hp_status = forms.ChoiceField(label="HP Status", choices=PACT_HP_CHOICES, required=False)
    dot_status = forms.ChoiceField(label="DOT Status", choices=PACT_DOT_CHOICES, required=False)
    artregimen = forms.ChoiceField(choices=PACT_REGIMEN_CHOICES, required=False)
    nonartregimen = forms.ChoiceField(choices=PACT_REGIMEN_CHOICES, required=False)
    hiv_care_clinic = forms.ChoiceField(choices=PACT_HIV_CLINIC_CHOICES)

    patient_notes = forms.CharField(widget = widgets.Textarea(attrs={'cols':80,'rows':5}), required=False)

    def __init__(self, request, casedoc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.casedoc = casedoc
        self.fields['hp'].choices = get_hp_choices()
        self.case_es = ReportCaseESView(request.domain)
        for name, field in self.fields.items():
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
                    ret[name] = value

        # hack, if any of the names, change remake the name and initials
        name_changed = False
        if 'first_name' in list(ret.keys()):
            name_changed = True
            first_name = ret['first_name']
        else:
            first_name = self.casedoc.first_name

        if 'last_name' in list(ret.keys()):
            name_changed = True
            last_name = ret['last_name']
        else:
            last_name = self.casedoc.last_name

        if name_changed:
            ret['name'] = '%s %s' % (first_name, last_name)
            ret['initials'] = '%s%s' % (first_name[0] if len(first_name) > 1 else '', last_name[0] if len(last_name) > 0 else '')

        return ret

    def clean_dob(self):
        if self.cleaned_data['dob'] is not None:
            return json_format_date(self.cleaned_data['dob'])
        else:
            return None

    def clean_mass_health_expiration(self):
        if self.cleaned_data['mass_health_expiration'] is not None:
            return json_format_date(self.cleaned_data['mass_health_expiration'])
        else:
            return None
