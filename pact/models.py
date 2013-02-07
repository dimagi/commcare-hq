from functools import partial
import uuid
from dateutil.parser import parser
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
from dimagi.utils.decorators.memoized import memoized
from pact import enums

from couchdbkit.schema.properties import ALLOWED_PROPERTY_TYPES
from pact.enums import TIME_LABEL_LOOKUP, PACT_SCHEDULES_NAMESPACE, DOT_ART, DOT_NONART, PACT_REGIMEN_CHOICES_FLAT_DICT, REGIMEN_CHOICES, PACT_DOMAIN
from pact.regimen import regimen_string_from_doc

ALLOWED_PROPERTY_TYPES.add(partial)

def make_uuid():
    return uuid.uuid4().hex

#placeholder for management of pact case models
from datetime import datetime, timedelta
from couchdbkit.ext.django.schema import StringProperty, DateTimeProperty, BooleanProperty, Document, DateProperty, SchemaListProperty, IntegerProperty

dp = parser()

class DOTSubmission(XFormInstance):
    @property
    def has_pillbox_check(self):
        pillbox_check_str = self.form['pillbox_check'].get('check', '')
        if len(pillbox_check_str) > 0:
            pillbox_check_data = simplejson.loads(pillbox_check_str)
            anchor_date = dp.parse(pillbox_check_data.get('anchor', '0000-01-01'))
        else:
            pillbox_check_str = {}
            anchor_date = datetime.min
        encounter_date = self.form['encounter_date'] #datetime already from couch
        return 'yes' if anchor_date.date() == encounter_date else 'no'

    @property
    def drilldown_url(self):
        from pact.reports.dot import PactDOTReport
        if self.form['case'].has_key('case_id'):
            case_id = self.form['case'].get('case_id', None)
        elif self.form['case'].has_key('@case_id'):
            case_id = self.form['case'].get('@case_id', None)
        else:
            case_id = None

        if case_id is not None:
            return PactDOTReport.get_url(*[PACT_DOMAIN]) + "?dot_patient=%s&submit_id=%s" % (case_id, self._id)
        else:
            return "#"
        pass
    class Meta:
        app_label='pact'


class PactPatientCase(CommCareCase):
#class PactPatientCase(Document):
    def __init__(self, *args, **kwargs):
        super(PactPatientCase, self).__init__(*args, **kwargs)

        self._set_display_methods()

    @memoized
    def get_user_map(self):
        domain_users = CommCareUser.by_domain(enums.PACT_DOMAIN)
        return dict((du.get_id, du.username_in_report) for du in domain_users)

    def _set_display_methods(self):
        properties =[
                    ('race', enums.PACT_RACE_CHOICES_DICT),
                     ('gender', enums.GENDER_CHOICES_DICT),
                     ('preferred_language', enums.PACT_LANGUAGE_CHOICES_DICT),
                     ('hp_status',enums.PACT_HP_CHOICES_DICT),
                     ('dot_status', enums.PACT_DOT_CHOICES_DICT),
                     ('artregimen',enums.PACT_REGIMEN_CHOICES_FLAT_DICT),
                     ('nonartregimen',enums.PACT_REGIMEN_CHOICES_FLAT_DICT),
                     ('hiv_care_clinic', enums.PACT_HIV_CLINIC_CHOICES_DICT),
                     ('primary_hp', self.get_user_map),
                     ]
        for prop, source_dict in properties:
            setattr(self, 'get_%s_display' % prop, partial(self._get_display_string, prop, source_dict))


    def update_providers(self, cc_user, provider_ids):
        from pact.api import submit_case_update_form
        for x in provider_ids:
            print x
        update_dict = dict(('provider%d' % ix, provider_id) for (ix, provider_id) in enumerate(provider_ids, start=1))
        submit_case_update_form(self, update_dict, cc_user)


    def get_provider_ids(self):
        for x in range(1,10):
            providerx = getattr(self, 'provider%d' % x, None)
            if providerx is not None and providerx != "":
                yield providerx

    @property
    def get_providers(self):
        """
        return a list of all the providers for this patient
        """
        from pact.api import get_all_providers
        all_providers = get_all_providers()
        pt_providers = list(self.get_provider_ids())

        providers_dict = dict((x.fields['id'], x.fields) for x in all_providers)
        #filtered= filter(lambda x: x.fields['id'] in pt_providers, all_providers)
        #return [x.fields for x in filtered]

        return [providers_dict[x] for x in pt_providers]


    def _get_display_string(self, attr, display_dict):
        attr_val = getattr(self, attr, None)
        if attr_val is not None:
            return display_dict.get(attr_val, attr_val)
        else:
            return ""
    def is_dot(self):
        dot_status = getattr(self, 'dot_status', None)
        print dot_status
        if dot_status is None:
            return False
        else:
            if dot_status.lower().startswith('dot'):
                return True
            else:
                return None

    def art_regimen_label_string(self):
        """
        representation of the labeled strings of the art regimen" morning,noon,evening
        """
        return regimen_string_from_doc(DOT_ART, self.to_json())

    def nonart_regimen_label_string(self):
        """
        representation of the labeled strings of the nonart regimen: morning,noon,evening, etc
        """
        return regimen_string_from_doc(DOT_NONART, self.to_json())

    def art_regimen_label_string_display(self):
        regimen_string = regimen_string_from_doc(DOT_ART, self.to_json())
        if regimen_string is None:
            return "No regimen"
#        elif regimen_string.startswith('Error,'):
#            return "[%s] %s" % (self.artregimen, regimen_string)
        else:
            return "[%s] %s" % (REGIMEN_CHOICES[int(self.art_properties()[enums.CASE_ART_REGIMEN_PROP])], PACT_REGIMEN_CHOICES_FLAT_DICT[regimen_string])

    def nonart_regimen_label_string_display(self):
        regimen_string = regimen_string_from_doc(DOT_NONART, self.to_json())
        if regimen_string is None:
            return "No regimen"
        elif regimen_string.startswith('Error,'):
            return "[%s] %s" % (self.nonartregimen, regimen_string)
        else:
            return "[%s] %s" % (REGIMEN_CHOICES[int(self.nonart_properties()[enums.CASE_NONART_REGIMEN_PROP])], PACT_REGIMEN_CHOICES_FLAT_DICT[regimen_string])

    def art_properties(self):
        return {
            enums.CASE_ART_REGIMEN_PROP: getattr(self, enums.CASE_ART_REGIMEN_PROP, None),
            'dot_a_one': getattr(self, 'dot_a_one', ''),
            'dot_a_two': getattr(self, 'dot_a_two', ''),
            'dot_a_three': getattr(self, 'dot_a_three', ''),
            'dot_a_four': getattr(self, 'dot_a_four', '')
        }

    def nonart_properties(self):
        return {
            enums.CASE_NONART_REGIMEN_PROP: getattr(self, enums.CASE_NONART_REGIMEN_PROP, None),
            'dot_n_one': getattr(self, 'dot_n_one', ''),
            'dot_n_two': getattr(self, 'dot_n_two', ''),
            'dot_n_three': getattr(self, 'dot_n_three', ''),
            'dot_n_four': getattr(self, 'dot_n_four', '')
        }

    @property
    def nonart_labels(self):
        for label in ['dot_n_one', 'dot_n_two', 'dot_n_three', 'dot_n_four']:
            val = getattr(self, label, '')
            if val != "" and val != None:
                yield val

    @property
    def art_labels(self):
        for label in ['dot_a_one', 'dot_a_two', 'dot_a_three', 'dot_a_four']:
            val = getattr(self, label, '')
            if val != "" and val != None:
                yield val


    def get_schedules(self, raw_json=False, reversed=False):
        if raw_json:
            obj = self.to_json()
        else:
            obj=self
        computed = obj['computed_']
        if computed.has_key(PACT_SCHEDULES_NAMESPACE):
            ret = [x for x in computed[PACT_SCHEDULES_NAMESPACE]]
            if not raw_json:
                ret = [CDotWeeklySchedule.wrap(x) for x in ret]
            if reversed:
                ret.reverse()
            return ret
        else:
            return []
    def rm_schedule(self):
        """
        Remove the tail from the schedule - does not save doc
        """
        schedules = self.get_schedules()[:-1]
        self._recompute_schedules(schedules)

    def _recompute_schedules(self, schedules):
        for ix, curr_sched in enumerate(schedules):
            #ensure that current ended is <= next ended
            next_sched = None
            if ix < len(schedules) - 1:
                next_sched = schedules[ix+1]
            else:
                #we are at the end
                if curr_sched.ended is not None:
                    curr_sched.ended = None
                    schedules[ix] = curr_sched

            if next_sched is not None:
                if curr_sched.ended is None:
                    #not good, there's a next
                    curr_sched.ended = next_sched.started - timedelta(seconds=1)
                    schedules[ix] = curr_sched
                if curr_sched.ended <= next_sched.started:
                    #ok, good
                    pass
        self['computed_'][PACT_SCHEDULES_NAMESPACE] = [x.to_json() for x in schedules]

    def set_schedule(self, new_schedule):
        """set the schedule as head of the schedule by accepting a cdotweeklychedule, does not save doc"""
        assert isinstance(new_schedule, CDotWeeklySchedule), "setting schedule instance must be a CDotWeeklySchedule class"
        #first, set all the others to inactive
        schedules = self.get_schedules()
        new_schedule.deprecated=False
        if new_schedule.started == None or new_schedule.started <= datetime.utcnow():
            new_schedule.started=datetime.utcnow()
        #recompute and make sure all schedules are closed time intervals
        schedules.append(new_schedule)
        self._recompute_schedules(schedules)




    def get_info_url(self):
        from pact.reports.patient import PactPatientInfoReport
        return PactPatientInfoReport.get_url( *[PACT_DOMAIN]) + "?patient_id=%s" % self._id

    def get_dot_url(self):
        from pact.reports.dot import PactDOTReport
        return PactDOTReport.get_url(*[PACT_DOMAIN]) + "?dot_patient=%s" % self._id



    @property
    def schedules(self):
        #patient_doc is the case doc
        computed = self['computed_']
        ret = {}

        def get_current(x):
            if x.ended is None and x.started <= datetime.utcnow():
                return True
            if x.ended is not None and x.ended <= datetime.utcnow():
                return False
            if x.started > datetime.utcnow():
                return False

            print "made it to the end somehow..."
            print '\n'.join(x.weekly_arr)
            return False

        if computed.has_key(PACT_SCHEDULES_NAMESPACE):
            schedule_arr = self.get_schedules()

            past = filter(lambda x: x.ended is not None and x.ended < datetime.utcnow(), schedule_arr)
            current = filter(get_current, schedule_arr)
            future = filter(lambda x: x.deprecated and x.started > datetime.utcnow(), schedule_arr)
            past.reverse()

#            print current
            if len(current) > 1:
                for x in current:
                    print '\n'.join(x.weekly_arr())

            ret['current_schedule'] = current[0]
            ret['past_schedules'] = past
            ret['future_schedules'] = future
        return ret


    @property
    def addresses(self):
        for ix in range(1,6):
            if hasattr(self, 'address%d' % ix) and hasattr(self, 'address%dtype' % ix):
                address = getattr(self, "address%d" % ix, None)
                if address is not None and address != "":
                    yield {'id': ix, 'address': address, "type": getattr(self, "address%dtype" % ix)}

    @property
    def phones(self):
        for ix in range(1,6):
            if hasattr(self, 'Phone%d' % ix) and hasattr(self, 'Phone%dType' % ix):
                number = getattr(self, "Phone%d" % ix, None)
                if number is not None and number != "":
                    yield {'id': ix, 'number': number, "type": getattr(self, "Phone%dType" % ix)}

    class Meta:
        app_label='pact'




class CDotWeeklySchedule(Document):
    """Weekly schedule where each day has a username"""
    schedule_id = StringProperty(default=make_uuid)

    sunday = StringProperty()
    monday = StringProperty()
    tuesday = StringProperty()
    wednesday = StringProperty()
    thursday = StringProperty()
    friday = StringProperty()
    saturday = StringProperty()


    comment = StringProperty()

    deprecated = BooleanProperty(default=False)

    started = DateTimeProperty(default=datetime.utcnow, required=True)
    ended = DateTimeProperty()

    created_by = StringProperty() #userid
    edited_by = StringProperty() #userid

    def weekly_arr(self):
        return [
            "Sun: %s" % self.sunday,
            "Mon: %s" % self.monday,
            "Tue: %s" % self.tuesday,
            "Wed: %s" % self.wednesday,
            "Thu: %s" % self.thursday,
            "Fri: %s" % self.friday,
            "Sat: %s" % self.saturday,
            "Deprecated: %s" % self.deprecated,
            "Started: %s" % self.started,
            "Ended: %s" % self.ended,
                ]

    class Meta:
        app_label='pact'



ADDENDUM_NOTE_STRING = "[AddendumEntry]"
class CObservation(Document):
    doc_id = StringProperty()
    patient = StringProperty() #case id

    pact_id = StringProperty() #patient pact id
    provider = StringProperty()

    encounter_date = DateTimeProperty()
    anchor_date = DateTimeProperty()
    observed_date = DateTimeProperty()

    submitted_date = DateTimeProperty()
    created_date = DateTimeProperty()

    is_art = BooleanProperty()
    dose_number=IntegerProperty()
    total_doses = IntegerProperty()
    adherence=StringProperty()

    # DOT_OBSERVATION_ types
    method=StringProperty()

    is_reconciliation = BooleanProperty(default=False)

    day_index = IntegerProperty()

    day_note = StringProperty() #if there's something for that particular day, then it'll be here
    day_slot = IntegerProperty() #new addition, if there's a slot for the day label, then retain it
    note = StringProperty() #this is for the overall note for that submission, will exist on the anchor date

    @property
    def obs_score(self):
        """Gets the relative score of the observation.
        """
        if self.method == "direct":
            return 3
        if self.method == "pillbox":
            return 2
        if self.method == "self":
            return 1



    @property
    def adinfo(self):
        """helper function to concatenate adherence and method to check for conflicts"""
        return ((self.is_art, self.dose_number, self.total_doses), "%s" % (self.adherence))


    #    def save(self):
    #        #override save as this is not a document but just a view
    #        pass


    def get_time_label(self):
        """
        old style way
        returns an English time label out of
        'Dose', 'Morning', 'Noon', 'Evening', 'Bedtime'
        """
        return TIME_LABEL_LOOKUP[self.total_doses][self.dose_number]

    @classmethod
    def get_time_labels(cls, total_doses):
        return TIME_LABEL_LOOKUP[total_doses]

    class Meta:
        app_label = 'pact'

    def __unicode__(self):
        return "Obs %s [%s] %d/%d" % (self.observed_date.strftime("%Y-%m-%d"), "ART" if self.is_art else "NonART", self.dose_number+1, self.total_doses)

    def __str__(self):
        return "Obs %s [%s] %d/%d" % (self.observed_date.strftime("%Y-%m-%d"), "ART" if self.is_art else "NonART", self.dose_number+1, self.total_doses)

    def __repr__(self):
        return simplejson.dumps(self.to_json(), indent=4)

class CObservationAddendum(Document):
#    sub_id = StringProperty(default=make_uuid)
    observed_date = DateProperty()
    art_observations = SchemaListProperty(CObservation)
    nonart_observations = SchemaListProperty(CObservation)
    created_by = StringProperty()
    created_date = DateTimeProperty()
    notes = StringProperty() #placeholder if need be
    class Meta:
        app_label = 'pact'


from signals import *
