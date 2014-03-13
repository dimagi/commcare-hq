from corehq.apps.reports.fields import BooleanField

class ShowOnlySurveyTraffic(BooleanField):
    label = "Show Only SMS from Surveys"
    slug = "show_only_survey_traffic"

