from functools import partial
import uuid
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import DocumentIndicatorDefinition, FormIndicatorDefinition
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from pact import enums

from couchdbkit.schema.properties import ALLOWED_PROPERTY_TYPES
from pact.enums import TIME_LABEL_LOOKUP, PACT_SCHEDULES_NAMESPACE, DOT_ART, DOT_NONART
from pact.regimen import regimen_string_from_doc

ALLOWED_PROPERTY_TYPES.add(partial)

def make_uuid():
    return uuid.uuid4().hex

#placeholder for management of pact case models
from datetime import datetime, timedelta
from couchdbkit.ext.django.schema import StringProperty, DateTimeProperty, BooleanProperty, Document, DateProperty, SchemaListProperty, IntegerProperty



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

    def _get_display_string(self, attr, display_dict):
        attr_val = getattr(self, attr, None)
        if attr_val is not None:
            return display_dict.get(attr_val, attr_val)
        else:
            return ""

    def art_regimen_label_string(self):
        """
        representation of the labeled strings of the art regimen
        """
        return regimen_string_from_doc(DOT_ART, self.to_json())

    def nonart_regimen_label_string(self):
        """
        representation of the labeled strings of the nonart regimen
        """
        return regimen_string_from_doc(DOT_NONART, self.to_json())

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
    def rm_schedule(self):
        """
        Remove the tail from the schedule
        """
        schedules= self.get_schedules()[:-1]
        self['computed_'][PACT_SCHEDULES_NAMESPACE] = [x.to_json() for x in schedules]
        self.save()

    def set_schedule(self, new_schedule):
        """set the schedule as head of the schedule by accepting a cdotweeklychedule"""
        #first, set all the others to inactive
        schedules = self.get_schedules()
        new_schedule.deprecated=False
        if new_schedule.started == None or new_schedule.started <= datetime.utcnow():
            new_schedule.started=datetime.utcnow()
        #recompute and make sure all schedules are closed time intervals
        for ix, curr_sched in enumerate(schedules):
            #ensure that current ended is <= next ended
            next_sched = None
            if ix < len(schedules) - 1:
                next_sched = schedules[ix+1]

            if next_sched is not None:
                if curr_sched.ended is None:
                    #not good, there's a next
                    curr_sched.ended = next_sched.started - timedelta(seconds=1)
                if curr_sched.ended <= next_sched.started:
                    #ok, good
                    pass
            else:
                #we're at the end
                #do nothing, assume it was created OK
                #curr_sched.deprecated=False
                pass

        schedules.append(new_schedule)
        self['computed_'][PACT_SCHEDULES_NAMESPACE] = [x.to_json() for x in schedules]
        self.save()
#        print schedules



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
                yield {'id': ix, 'address': getattr(self, "address%d" % ix), "type": getattr(self, "address%dtype" % ix)}

    @property
    def phones(self):
        for ix in range(1,6):
            if hasattr(self, 'Phone%d' % ix) and hasattr(self, 'Phone%dType' % ix):
                yield {'id': ix, 'number': getattr(self, "Phone%d" % ix), "type": getattr(self, "Phone%dType" % ix)}

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


from .signals import *
