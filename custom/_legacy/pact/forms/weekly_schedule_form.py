from datetime import datetime
import uuid
from django import forms
from django.forms import widgets
from django.contrib.auth.models import User
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from pact.enums import PACT_DOMAIN

DAYS_OF_WEEK = ['sunday','monday','tuesday','wednesday','thursday','friday','saturday']

def make_uuid():
    return uuid.uuid4().hex

class ScheduleForm(forms.Form):
    """
    Form to provide for simple editing/commenting on an inbound progrssnote for PACT
    """

    #http://techblog.appnexus.com/2011/easy-web-forms-with-knockout-js/

    sunday = forms.ChoiceField(choices=[], required=False)
    monday = forms.ChoiceField(choices=[], required=False)
    tuesday = forms.ChoiceField(choices=[], required=False)
    wednesday = forms.ChoiceField(choices=[], required=False)
    thursday = forms.ChoiceField(choices=[], required=False)
    friday = forms.ChoiceField(choices=[], required=False)
    saturday = forms.ChoiceField(choices=[], required=False)

    comment = forms.CharField(required=False)
    active_date = forms.DateField(help_text="Date this schedule should be made active.  Note active time is 12:01am the day you choose.",
                                  required=True, widget=widgets.TextInput(), initial= datetime.utcnow().strftime("%m/%d/%Y"))#attrs={"value": datetime.utcnow().strftime("%m-%d-%Y")}))

    schedule_id = forms.CharField(widget=widgets.HiddenInput(), initial=make_uuid)

    @memoized
    def get_user_choices(self):
        users = CommCareUser.by_domain(PACT_DOMAIN)
#        return [(x._id, x.raw_username) for x in users]
        yield (None, "-- unassigned --")
        for x in users:
            yield (x.raw_username, x.raw_username)


    def __init__(self, *args, **kwargs):
        super(ScheduleForm, self).__init__(*args, **kwargs)

        user_choices = list(self.get_user_choices())
        for day in DAYS_OF_WEEK:
            self.fields[day].choices = user_choices

        #http://stackoverflow.com/questions/10403094/using-knockout-js-with-django-forms
#        for name, field in self.fields.items():
#            field.widget.attrs['class'] = 'schedule_form_field'
            # this could be used in your case if the Django field name is the
            # same as the KO.js field name
#            field.widget.attrs['data-bind'] = 'value: new_%s' % name
