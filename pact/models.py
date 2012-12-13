from functools import partial
import uuid
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import DocumentIndicatorDefinition, FormIndicatorDefinition
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from pact import enums

from couchdbkit.schema.properties import ALLOWED_PROPERTY_TYPES
from pact.enums import TIME_LABEL_LOOKUP, PACT_SCHEDULES_NAMESPACE

ALLOWED_PROPERTY_TYPES.add(partial)

def make_uuid():
    return uuid.uuid4().hex

#placeholder for management of pact case models
from datetime import datetime
from couchdbkit.ext.django.schema import StringProperty, DateTimeProperty, BooleanProperty, Document, DateProperty, SchemaListProperty, IntegerProperty


#class PactDOTIndicatorDefinition(FormIndicatorDefinition):
#    namespace = StringProperty()
#    domain = StringProperty()
#    slug = StringProperty()
#    version = IntegerProperty()
#    class_path = StringProperty()
#
#
#    def get_value(self, doc):
#        dots_json = doc['form']['case']['update']['dots']
#        if isinstance(dots_json, str) or isinstance(dots_json, unicode):
#            json_dots = simplejson.loads(dots_json)
#            return json_dots
#        else:
#            return {}
#
#    def get_existing_value(self, doc):
#        try:
#            return doc.computed_.get(self.namespace, {}).get(self.slug, {}).get('value')
#        except AttributeError:
#            return None




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


    def get_schedules(self, raw_json=False, reversed=False):
        if raw_json:
            obj = self.to_json()
        else:
            obj=self
        computed = obj['computed_']
        if computed.has_key(PACT_SCHEDULES_NAMESPACE):
            ret = [x for x in computed[PACT_SCHEDULES_NAMESPACE]]
            if reversed:
                ret.reverse()
            return ret

    def set_schedule(self, new_schedule):
        """set the schedule as head of the schedule by accepting a cdotweeklychedule"""
        #first, set all the others to inactive

        schedules = self.get_schedules()
        new_schedule.deprecated=False
        if new_schedule.started == None or new_schedule.started <= datetime.utcnow():
            new_schedule.started=datetime.utcnow()
            for sched in schedules:
                if not sched.deprecated:
                    #sched.deprecated=True
                    sched.ended=datetime.utcnow()
#                    sched.save()
        elif new_schedule.started > datetime.utcnow():
            #if it's in the future, then don't deprecate the future schedule, just procede along and let the system set the dates correctly
            pass
#        self.weekly_schedule.append(new_schedule)
#        self.save()


    @property
    def schedules(self):
        #patient_doc is the case doc
        computed = self['computed_']
        ret = {}

        def get_current(x):
            if x.deprecated:
                return False
            if x.ended is None and x.started < datetime.utcnow():
                return True
            if x.ended < datetime.utcnow():
                return False

            print "made it to the end somehow..."
            print '\n'.join(x.weekly_arr)
            return False

        if computed.has_key(PACT_SCHEDULES_NAMESPACE):
            schedule_arr = [CDotWeeklySchedule.wrap(x) for x in self.get_schedules()]

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
    method=StringProperty()

    is_reconciliation = BooleanProperty(default=False)

    day_index = IntegerProperty()

    day_note = StringProperty() #if there's something for that particular day, then it'll be here
    day_slot = IntegerProperty() #new addition, if there's a slot for the day label, then retain it
    note = StringProperty() #this is for the overall note for that submission, will exist on the anchor date


    def __unicode__(self):
        return simplejson.dumps(self.to_json())


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

    def __unicode__(self):
        return "Dots Observation: %s on %s" % (self.observed_date, self.anchor_date)

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
        return "Obs %s [%s] %d/%d" % (self.observed_date.strftime("%Y-%m-%d"), "ART" if self.is_art else "NonART", self.dose_number, self.total_doses)

    def __str__(self):
        return "Obs %s [%s] %d/%d" % (self.observed_date.strftime("%Y-%m-%d"), "ART" if self.is_art else "NonART", self.dose_number, self.total_doses)

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
