import pytz
from django.utils.translation import ugettext as _
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from custom.fri.models import PROFILE_A, PROFILE_B, PROFILE_C, PROFILE_D, PROFILE_E, PROFILE_F, PROFILE_G, PROFILE_H, PROFILE_DESC
from custom.fri.api import get_interactive_participants
from datetime import datetime, date, timedelta
from dimagi.utils.parsing import json_format_date


class InteractiveParticipantFilter(BaseSingleOptionFilter):
    slug = "participant"
    label = _("Participant")

    @property
    def options(self):
        cases = get_interactive_participants(self.domain)
        return [(case.get_id, case.name) for case in cases]

class RiskProfileFilter(BaseSingleOptionFilter):
    slug = "risk_profile"
    label = _("Risk Profile")
    default_text = _("All")

    @property
    def options(self):
        return [
            (PROFILE_A, PROFILE_DESC[PROFILE_A]),
            (PROFILE_B, PROFILE_DESC[PROFILE_B]),
            (PROFILE_C, PROFILE_DESC[PROFILE_C]),
            (PROFILE_D, PROFILE_DESC[PROFILE_D]),
            (PROFILE_E, PROFILE_DESC[PROFILE_E]),
            (PROFILE_F, PROFILE_DESC[PROFILE_F]),
            (PROFILE_G, PROFILE_DESC[PROFILE_G]),
            (PROFILE_H, PROFILE_DESC[PROFILE_H]),
        ]

class SurveyDateSelector(BaseSingleOptionFilter):
    """
    Single option filter for selecting the dates on which surveys were
    sent out.
    """
    slug = "survey_report_date"
    label = _("Show participants who where sent a survey on")
    default_text = _("Choose...")

    @classmethod
    def get_value(cls, *args, **kwargs):
        default = json_format_date(cls.get_date_choices()[-1])
        return super(SurveyDateSelector, cls).get_value(*args, **kwargs) or default

    @classmethod
    def get_date_choices(cls):
        next_date = date(2014, 3, 18)
        last_date = pytz.utc.localize(datetime.utcnow())
        last_date = last_date.astimezone(pytz.timezone("US/Pacific"))
        last_date = last_date.date()
        dates = []
        while next_date <= last_date:
            dates.append(next_date)
            next_date += timedelta(days=7)
        return dates

    def __init__(self, *args, **kwargs):
        super(SurveyDateSelector, self).__init__(*args, **kwargs)
        self._date_choices = SurveyDateSelector.get_date_choices()

    @property
    def options(self):
        result = []
        for date in sorted(self._date_choices, reverse=True):
            result.append((json_format_date(date), date.strftime("%m/%d/%y")))
        return result

