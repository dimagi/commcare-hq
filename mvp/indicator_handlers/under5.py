import datetime
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized

class Under5Indicators(object):

    def __init__(self, domain, user_ids, startdate, enddate):
        """
            domain should be the domain name
            users should be a list of user_ids or a single user id to compute these indicators.
        """
        if not (isinstance(startdate, datetime.datetime) and isinstance(enddate, datetime.datetime)):
            raise ValueError("startdate and enddate must be a datetime")
        self.domain = domain
        if not isinstance(user_ids, list):
            user_ids = [user_ids]
        self.user_ids = user_ids
        self.startdate = startdate
        self.enddate = enddate

    @property
    def indicators(self):
        return dict(
            under5=dict(
                title="No. of Under-5s",
                value=self.get_base_indicator("under5")
            ),
            under5_danger_signs=dict(
                title="No. of Under-5s Referred for Danger Signs",
                value=self.get_base_indicator("under5_danger_signs")
            ),
            under5_fever=dict(
                title="No. of Under-5s with uncomplicated Fever",
                value=self.get_base_indicator("under5_fever")
            ),
            under5_fever_rdt=dict(
                title="Proportion of Under-5s with uncomplicated fever who received RDT test",
                numerator=self.get_base_indicator("under5_fever rdt_test_received"),
                denominator=self.get_base_indicator("under5_fever")
            ),
            under5_fever_rdt_positive=dict(
                title="Proportion of Under-5s with uncomplicated fever who recieved RDT test and were RDT positive",
                numerator=self.get_base_indicator("under5_fever rdt_test_received rdt_test_positive"),
                denominator=self.get_base_indicator("under5_fever rdt_test_received")
            ),
            under5_fever_rdt_positive_medicated=dict(
                title="Proportion of Under-5s with uncomplicated fever who recieved RDT test and were RDT positive",
                numerator=self.get_base_indicator("under5_fever rdt_test_received rdt_test_positive anti_malarial"),
                denominator=self.get_base_indicator("under5_fever rdt_test_received rdt_test_positive")
            ),
            under5_rdt_not_received=dict(
                title="Proportion of Under-5s with uncomplicated fever who did NOT receive RDT "
                      "test due to 'RDT not available' with CHW",
                numerator=self.get_base_indicator('under5_fever rdt_not_available'),
                denominator=self.get_base_indicator("under5_fever")
            ),
            under5_diarrhea=dict(
                title="No. of Under-5s with uncomplicated Fever",
                value=self.get_base_indicator("under5_diarrhea")
            )
        )

    @memoized
    def get_base_indicator(self, prefix):
        totals = 0
        for user_id in self.user_ids:
            couch_key = ["user", self.domain, user_id, prefix]
            data = get_db().view('mvp/under5_child_health',
                reduce=True,
                startkey=couch_key+[self.startdate.isoformat()],
                endkey=couch_key+[self.enddate.isoformat()]
            ).first()
            if data:
                totals += data.get('value', 0)
        return  totals