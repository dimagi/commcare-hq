from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.reports.dont_use.fields import BooleanField


class ShowOnlySurveyTraffic(BooleanField):
    label = "Show Only SMS from Surveys"
    slug = "show_only_survey_traffic"

