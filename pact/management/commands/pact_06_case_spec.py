from corehq.apps.cloudcare.models import CaseSpec, CasePropertySpec, SelectChoice
from django.core.management.base import NoArgsCommand
from pact.enums import PACT_DOMAIN, PACT_CASE_TYPE, PACT_HP_CHOICES, GENDER_CHOICES, PACT_DOT_CHOICES
from pact.reports.patient_list import PactPrimaryHPField

class Command(NoArgsCommand):
    help = "Create or update the CaseSpec for PACT Cases"
    option_list = NoArgsCommand.option_list + (
    )

    #http://localhost:8000/a/pact/cloudcare/cases/view/<case_id> #0bd56681dce2b7a5140f75266d1df9c9

    def handle_noargs(self, **options):
        pact_spec = CaseSpec.get_suggested(PACT_DOMAIN, case_type=PACT_CASE_TYPE)
        specs = pact_spec.all()
        if len(specs) > 0:
            print "Found specs - purging"
            for spec in specs:
                CaseSpec.get_db().delete_doc(spec)


        print "regenerating case specs for %s.%s" % (PACT_DOMAIN, PACT_CASE_TYPE)


        newspec = CaseSpec(domain=PACT_DOMAIN, name="PACT Case", case_type=PACT_CASE_TYPE)
        newspec.save()

        properties = []

#        properties.append(CasePropertySpec(label='arm', key='arm', type='choice', choices=))
        spec_hp_choices = [SelectChoice(stringValue=x[0], label={'en': x[1]}) for x in  PACT_HP_CHOICES]
        spec_dot_choices = [SelectChoice(stringValue=x[0], label={'en': x[1]}) for x in PACT_DOT_CHOICES]
        spec_gender_choices = [SelectChoice(stringValue=x[0], label={'en': x[1]}) for x in GENDER_CHOICES]
        primary_hp_choices = [SelectChoice(stringValue=x['val'], label=dict(en=x['text'])) for x in PactPrimaryHPField.get_chws()]


        properties.append(CasePropertySpec(key='hp_status', label={'en':'HP Status'}, type='select', choices=spec_hp_choices))
        properties.append(CasePropertySpec(key='dot_status', label={'en': 'DOT Status'}, type='select', choices=spec_dot_choices))
        properties.append(CasePropertySpec(key='gender', label={'en': 'Sex'}, type='select', choices=spec_gender_choices))
        properties.append(CasePropertySpec(key='birthdate', label={'en': 'DOB'}, type='date'))
        properties.append(CasePropertySpec(key='notes', label={'en': 'Notes'}, type='string'))
        properties.append(CasePropertySpec(key='mass_health_expiration',  label={'en': 'Mass Health Expiration Date'}, type='date'))
        properties.append(CasePropertySpec(key='ssn', label={'en': 'SSN'}, type='string'))
        properties.append(CasePropertySpec(key='hp', label={'en': 'Primary HP'}, type='select', choices=primary_hp_choices))
        newspec.propertySpecs = properties
        newspec.save()


        #add propreties
#        arm = forms.ChoiceField(label="PACT ARM", choices=PACT_ARM_CHOICES)
#        hp_status = forms.ChoiceField(label="HP Status", choices=PACT_HP_CHOICES, required=False)
#        dot_status = forms.ChoiceField(label="DOT Status", choices=PACT_DOT_CHOICES, required=False)
#        art_regimen = forms.ChoiceField(choices=REGIMEN_CHOICES, required=False)
#        non_art_regimen = forms.ChoiceField(choices=REGIMEN_CHOICES, required=False)
#
#        #primary_hp = forms.ChoiceField(label="Primary health promoter", choices=tuple([(x, x) for x in hack_pact_usernames])) #old style pre actor setup
#        primary_hp = forms.ChoiceField(label="Primary health promoter", choices=())
#        notes = forms.CharField(widget = widgets.Textarea(attrs={'cols':80,'rows':5}), required=False)
#        #source: http://stackoverflow.com/questions/1513502/django-how-to-format-a-datefields-date-representation
#        birthdate = forms.DateField(input_formats=['%m/%d/%Y'], widget=forms.DateInput(format = '%m/%d/%Y', attrs={'class': 'jqui-dtpk'}))
#        gender = forms.ChoiceField(choices=GENDER_CHOICES)
#
#
#        race = forms.ChoiceField(choices=PACT_RACE_CHOICES)
#        hiv_care_clinic = forms.ChoiceField(choices=PACT_HIV_CLINIC_CHOICES)
#        preferred_language = forms.ChoiceField(choices=PACT_LANGUAGE_CHOICES)
#
#        mass_health_expiration = forms.DateField(label = "Mass Health expiration Date", input_formats=['%m/%d/%Y',''], widget=forms.DateInput(format = '%m/%d/%Y'), required=False)
#        ssn = forms.CharField(label="Social Security Number", required=False)


