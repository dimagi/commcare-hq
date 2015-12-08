REPORT_INCIDENT_XMLNS = 'http://openrosa.org/formdesigner/A12E46B1-7ED8-4DE3-B7BB-358219CC6994'
FOLLOWUP_FORM_XMLNS = 'http://openrosa.org/formdesigner/9457DE46-E640-4F6E-AD9A-F9AC9FDA35E6'
IGA_FORM_XMLNS = 'http://openrosa.org/formdesigner/B4BAF20B-4337-409D-A446-FD4A0C8D5A9A'
OUTREACH_FORM_XMLNS = 'http://openrosa.org/formdesigner/B5C415BB-456B-49BE-A7AF-C5E7C9669E34'


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
