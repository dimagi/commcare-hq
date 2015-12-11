from custom.apps.cvsu.models import REPORT_INCIDENT_XMLNS, FOLLOWUP_FORM_XMLNS


class CVSUFilters(object):
    def __init__(self, form):
        self.form = form['form']
        self.xmlns = form['xmlns']

    def filter_action(self, action):
        return self.xmlns == REPORT_INCIDENT_XMLNS and self.form.get('actions_to_resolve_case') == action

    def filter_outcome(self, outcome, xmlns=None):
        if xmlns:
            return self.xmlns == xmlns and self.form.get('mediation_outcome') == outcome

        return (self.xmlns == REPORT_INCIDENT_XMLNS and self.form.get('mediation_outcome') == outcome) \
            or (self.xmlns == FOLLOWUP_FORM_XMLNS and self.form.get('mediation_outcome') == outcome)

    def filter_immediate_referral_org(self, org):
        return (
            self.xmlns == REPORT_INCIDENT_XMLNS and
            org in self.form.get('immediate_referral_organisation', '').split(' ')
        )

    def filter_referral_org(self, org):
        meditation_referral = self.form.get('mediation_referral', '').split(' ')
        return (
            self.xmlns in [REPORT_INCIDENT_XMLNS, FOLLOWUP_FORM_XMLNS] and org in meditation_referral
        )

    def filter_service(self, service):
        return (
            self.xmlns == REPORT_INCIDENT_XMLNS and service in self.form.get('immediate_services', '').split(' ')
        )

    def filter_abuse(self, category):
        return (
            self.xmlns == REPORT_INCIDENT_XMLNS and category in self.form.get('abuse_category', '').split(' ')
        )


def dynamic_date_aggregation(column, date_column):
    column.date_aggregation_column = date_column
    return column
