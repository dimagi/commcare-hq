from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext as _
import uuid
from dateutil.parser import parser
import json
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from memoized import memoized
from dimagi.utils.parsing import json_format_date
from pact import enums

from pact.enums import (
    DOT_ART,
    DOT_NONART,
    PACT_DOMAIN,
    PACT_REGIMEN_CHOICES_FLAT_DICT,
    PACT_SCHEDULES_NAMESPACE,
    REGIMEN_CHOICES,
)
from pact.regimen import regimen_string_from_doc
import six
from six.moves import range

from corehq.util.python_compatibility import soft_assert_type_text


def make_uuid():
    return uuid.uuid4().hex

from datetime import datetime, timedelta
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateProperty,
    IntegerProperty,
    OldDateTimeProperty,
    OldDocument,
    SchemaListProperty,
    StringProperty,
)

dp = parser()


class DOTSubmission(XFormInstance):

    @property
    def has_pillbox_check(self):
        pillbox_check_str = self.form['pillbox_check'].get('check', '')
        if len(pillbox_check_str) > 0:
            pillbox_check_data = json.loads(pillbox_check_str)
            anchor_date = dp.parse(pillbox_check_data.get('anchor', '0000-01-01'))
        else:
            anchor_date = datetime.min
        # datetime already from couch
        encounter_date = self.form['encounter_date']
        return 'yes' if anchor_date.date() == encounter_date else 'no'

    @property
    def drilldown_url(self):
        from pact.reports.dot import PactDOTReport
        if 'case_id' in self.form['case']:
            case_id = self.form['case'].get('case_id', None)
        elif '@case_id' in self.form['case']:
            case_id = self.form['case'].get('@case_id', None)
        else:
            case_id = None

        if case_id is not None:
            return PactDOTReport.get_url(*[PACT_DOMAIN]) + "?dot_patient=%s&submit_id=%s" % (case_id, self._id)
        else:
            return "#"
        pass

    class Meta(object):
        app_label = 'pact'


class PactPatientCase(CommCareCase):

    class Meta(object):
        app_label = 'pact'

    @property
    def gender_display(self):
        return self._get_display_string('gender', enums.GENDER_CHOICES_DICT)

    @property
    def race_display(self):
        return self._get_display_string('race', enums.PACT_RACE_CHOICES_DICT)

    @property
    def hp_status_display(self):
        return self._get_display_string(
            'hp_status', enums.PACT_HP_CHOICES_DICT)

    @property
    def dot_status_display(self):
        return self._get_display_string(
            'dot_status', enums.PACT_DOT_CHOICES_DICT)

    @property
    def hiv_care_clinic_display(self):
        return self._get_display_string(
            'hiv_care_clinic', enums.PACT_HIV_CLINIC_CHOICES_DICT
        )

    def update_providers(self, cc_user, provider_ids):
        from pact.api import submit_case_update_form
        update_dict = {'provider%d' % ix: provider_id
                       for ix, provider_id in enumerate(provider_ids, start=1)}
        submit_case_update_form(self, update_dict, cc_user)

    def get_provider_ids(self):
        for x in range(1, 10):
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

        providers_dict = {x.fields['id']: x.fields for x in all_providers}

        return [providers_dict[x] for x in pt_providers if x in providers_dict]

    def _get_display_string(self, attr, display_dict):
        attr_val = getattr(self, attr, None)
        if attr_val is not None:
            return display_dict.get(attr_val, attr_val)
        else:
            return ""

    def is_dot(self):
        dot_status = getattr(self, 'dot_status', None)
        if dot_status is None:
            return False
        else:
            if dot_status.lower().startswith('dot'):
                return True
            else:
                return None

    def art_regimen_label_string(self):
        """
        representation of the labeled strings
        of the art regimen: morning, noon, evening
        """
        return regimen_string_from_doc(DOT_ART, self.to_json())

    def nonart_regimen_label_string(self):
        """
        representation of the labeled strings
        of the nonart regimen: morning, noon, evening, etc
        """
        return regimen_string_from_doc(DOT_NONART, self.to_json())

    def art_regimen_label_string_display(self):
        regimen_string = regimen_string_from_doc(DOT_ART, self.to_json())
        if regimen_string is None:
            return "No regimen"
        elif regimen_string.startswith('Error,'):
            return "[%s] %s" % (REGIMEN_CHOICES[int(self.art_properties()[enums.CASE_ART_REGIMEN_PROP])], regimen_string)
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
            if val != "" and val is not None:
                yield val

    @property
    def art_labels(self):
        for label in ['dot_a_one', 'dot_a_two', 'dot_a_three', 'dot_a_four']:
            val = getattr(self, label, '')
            if val != "" and val is not None:
                yield val

    def get_schedules(self, raw_json=False, reversed=False):
        obj = self.to_json()
        computed = obj['computed_']
        if PACT_SCHEDULES_NAMESPACE in computed:
            ret = [x for x in computed[PACT_SCHEDULES_NAMESPACE]]
            if not raw_json:
                ret = [CDotWeeklySchedule.wrap(dict(x)) for x in ret]
            if reversed:
                ret.reverse()
            return ret
        else:
            return []

    def rm_last_schedule(self):
        """
        Remove the tail from the schedule - does not save doc
        """
        schedules = self.get_schedules()[:-1]
        self._recompute_schedules(schedules)

    def _recompute_schedules(self, schedules):
        schedules = sorted(schedules, key=lambda x: x.started)
        for ix, curr_sched in enumerate(schedules):
            # ensure that current ended is <= next ended
            next_sched = None

            if ix < len(schedules) - 1:
                next_sched = schedules[ix+1]
            else:
                # we are at the end
                if curr_sched.ended is not None:
                    curr_sched.ended = None
                    schedules[ix] = curr_sched

            if next_sched is not None:
                if curr_sched.ended is None:
                    # not good, there's a next
                    curr_sched.ended = next_sched.started - timedelta(seconds=1)
                    schedules[ix] = curr_sched
                if curr_sched.ended <= next_sched.started:
                    # ok, good
                    pass

        self['computed_'][PACT_SCHEDULES_NAMESPACE] = [x.to_json() for x in schedules]

    def set_schedule(self, new_schedule):
        """
        Set the schedule as head of the schedule.
        Does not save the case document.
        """
        assert isinstance(new_schedule, CDotWeeklySchedule), \
            "setting schedule instance must be a CDotWeeklySchedule class"
        # first, set all the others to inactive
        schedules = self.get_schedules()
        new_schedule.deprecated = False
        if new_schedule.started is None or new_schedule.started <= datetime.utcnow():
            new_schedule.started = datetime.utcnow()
        # recompute and make sure all schedules are closed time intervals
        schedules.append(new_schedule)
        self._recompute_schedules(schedules)

    def get_info_url(self):
        from pact.reports.patient import PactPatientInfoReport
        return PactPatientInfoReport.get_url(*[PACT_DOMAIN]) + "?patient_id=%s" % self._id

    @property
    def current_schedule(self):
        try:
            return self.schedules['current_schedule']
        except (KeyError, IndexError):
            return None

    @property
    @memoized
    def schedules(self):
        # patient_doc is the case doc
        computed = self['computed_']
        ret = {}

        if PACT_SCHEDULES_NAMESPACE in computed:
            schedule_arr = self.get_schedules()

            past = [x for x in schedule_arr if x.ended is not None and x.ended < datetime.utcnow()]
            current = [x for x in schedule_arr if x.is_current]
            future = [x for x in schedule_arr if x.deprecated and x.started > datetime.utcnow()]
            past.reverse()

            ret['current_schedule'] = current[0]
            ret['past_schedules'] = past
            ret['future_schedules'] = future
        return ret

    @property
    def addresses(self):
        for ix in range(1, 6):
            if hasattr(self, 'address%d' % ix) and hasattr(self, 'address%dtype' % ix):
                address = getattr(self, "address%d" % ix, None)
                if address is not None and address != "":
                    yield {'id': ix, 'address': address, "type": getattr(self, "address%dtype" % ix)}

    @property
    def phones(self):
        for ix in range(1, 6):
            if hasattr(self, 'Phone%d' % ix) and hasattr(self, 'Phone%dType' % ix):
                number = getattr(self, "Phone%d" % ix, None)
                if number is not None and number != "":
                    yield {'id': ix, 'number': number, "type": getattr(self, "Phone%dType" % ix)}
  
    @property
    def related_cases_columns(self):
        return [
            {
                'name': _('Status'),
                'expr': "status",
            },
            {
                'name': _('Follow-Up Date'),
                'expr': "date_followup",
                'parse_date': True,
                'timeago': True,
            },
            {
                'name': _('Date Modified'),
                'expr': "modified_on",
                'parse_date': True,
                'timeago': True,
            }
        ]

    @property
    def related_type_info(self):
        """For Care Plan module"""
        PACT_CLOUD_APP_ID = "615bff7178e2a14eeddd2cddbed60b79" 

        return {
            "cc_path_client": {
                "case_id_attr": "case_id",
                "child_type": "pact_careplan_goal",
            },
            "pact_careplan_goal": {
                'type_name': _("Goal"),
                'open_sortkeys': [['date_followup', 'asc']],
                'closed_sortkeys': [['closed_on', 'desc']],

                # should get these automatically from xmlns
                "app_id": PACT_CLOUD_APP_ID,
                "edit_module_id": "1",
                "edit_form_id": "3",
                "create_module_id": "1",
                "create_form_id": "0",
                "case_id_attr": "case_id_goal",
                "child_type": "pact_careplan_task",
                "description_property": "description",

                #'create_form_xmlns': "http://dev.commcarehq.org/pact/careplan/goal/create",
                #'update_form_xmlns': "http://dev.commcarehq.org/pact/careplan/goal/update"
            },
            "pact_careplan_task": {
                'type_name': _("Task"),
                'open_sortkeys': [['date_followup', 'asc']],
                'closed_sortkeys': [['closed_on', 'desc']],
               
                'app_id': PACT_CLOUD_APP_ID,
                "edit_module_id": "1",
                "edit_form_id": "2",
                "create_module_id": "1",
                "create_form_id": "1",
                "case_id_attr": "case_id_task",
                "description_property": "description",

                #'create_form_xmlns': "http://dev.commcarehq.org/pact/careplan/task/create",
                #'update_form_xmlns': "http://dev.commcarehq.org/pact/careplan/task/update"
            },
        }


class CDotWeeklySchedule(OldDocument):
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

    started = OldDateTimeProperty(default=datetime.utcnow, required=True)
    ended = OldDateTimeProperty()

    created_by = StringProperty()  # user id
    edited_by = StringProperty()  # user id

    @property
    def is_current(self):
        now = datetime.utcnow()
        return self.started <= now and (self.ended is None or self.ended > now)

    class Meta(object):
        app_label = 'pact'


ADDENDUM_NOTE_STRING = "[AddendumEntry]"


@six.python_2_unicode_compatible
class CObservation(OldDocument):
    doc_id = StringProperty()
    patient = StringProperty()  # case id

    pact_id = StringProperty()  # patient pact id
    provider = StringProperty()

    encounter_date = OldDateTimeProperty()
    anchor_date = OldDateTimeProperty()
    observed_date = OldDateTimeProperty()

    submitted_date = OldDateTimeProperty()
    created_date = OldDateTimeProperty()

    is_art = BooleanProperty()
    dose_number = IntegerProperty()
    total_doses = IntegerProperty()
    adherence = StringProperty()

    # DOT_OBSERVATION_ types
    method = StringProperty()

    is_reconciliation = BooleanProperty(default=False)

    day_index = IntegerProperty()

    # if there's something for that particular day, then it'll be here
    day_note = StringProperty()
    # new addition, if there's a slot for the day label, then retain it
    day_slot = IntegerProperty()
    # this is for the overall note for that submission,
    # will exist on the anchor date
    note = StringProperty()

    @classmethod
    def wrap(cls, obj):
        ints = ['dose_number', 'total_doses', 'day_index', 'day_slot']
        for prop_name in ints:
            val = obj.get(prop_name)
            if val and isinstance(val, six.string_types):
                soft_assert_type_text(val)
                obj[prop_name] = int(val)
        return super(CObservation, cls).wrap(obj)

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

    class Meta(object):
        app_label = 'pact'

    def __str__(self):
        return "Obs %s [%s] %d/%d" % (json_format_date(self.observed_date), "ART" if self.is_art else "NonART", self.dose_number+1, self.total_doses)

    def __repr__(self):
        return json.dumps(self.to_json(), indent=4)


class CObservationAddendum(OldDocument):
    observed_date = DateProperty()
    art_observations = SchemaListProperty(CObservation)
    nonart_observations = SchemaListProperty(CObservation)
    created_by = StringProperty()
    created_date = OldDateTimeProperty()
    notes = StringProperty()  # placeholder if need be

    class Meta(object):
        app_label = 'pact'


from .signals import *
