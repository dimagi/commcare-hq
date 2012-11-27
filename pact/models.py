from functools import partial
import uuid
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from pact import enums

from couchdbkit.schema.properties import ALLOWED_PROPERTY_TYPES
ALLOWED_PROPERTY_TYPES.add(partial)

def make_uuid():
    return uuid.uuid4().hex

#placeholder for management of pact case models
from datetime import datetime
from couchdbkit.ext.django.schema import StringProperty, DateTimeProperty, BooleanProperty, Document


class PactPatientCase(CommCareCase):


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
        app_label='pactpatient'
