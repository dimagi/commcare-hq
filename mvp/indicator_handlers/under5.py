import datetime
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from mvp.indicator_handlers import IndicatorHandler

class Under5IndicatorHandler(IndicatorHandler):

    @property
    @memoized
    def indicators(self):
        return dict(
            under5=dict(
                title="No. of Under-5s",
                get_value=lambda: self.get_base_indicator("under5")
            ),
            under5_danger_signs=dict(
                title="No. of Under-5s Referred for Danger Signs",
                get_value=lambda: self.get_base_indicator("under5_danger_signs")
            ),
            under5_fever=dict(
                title="No. of Under-5s with uncomplicated Fever",
                get_value=lambda: self.get_base_indicator("under5_fever")
            ),
            under5_fever_rdt=dict(
                title="Proportion of Under-5s with uncomplicated fever who received RDT test",
                get_value=lambda: dict(
                        numerator=self.get_base_indicator("under5_fever rdt_test_received"),
                        denominator=self.get_base_indicator("under5_fever")
                    )
            ),
            under5_fever_rdt_positive=dict(
                title="Proportion of Under-5s with uncomplicated fever who recieved RDT test and were RDT positive",
                get_value=lambda: dict(
                        numerator=self.get_base_indicator("under5_fever rdt_test_received rdt_test_positive"),
                        denominator=self.get_base_indicator("under5_fever rdt_test_received")
                    )
            ),
            under5_fever_rdt_positive_medicated=dict(
                title="Proportion of Under-5's with positive RDT result who received antimalarial/ADT medication",
                get_value=lambda: dict(
                        numerator=self.get_base_indicator("under5_fever rdt_test_received rdt_test_positive anti_malarial"),
                        denominator=self.get_base_indicator("under5_fever rdt_test_received rdt_test_positive")
                    )
            ),
            under5_fever_rdt_not_received=dict(
                title="Proportion of Under-5s with uncomplicated fever who did NOT receive RDT "
                      "test due to 'RDT not available' with CHW",
                get_value=lambda: dict(
                        numerator=self.get_base_indicator('under5_fever rdt_not_available'),
                        denominator=self.get_base_indicator("under5_fever")
                    )
            ),
            under5_diarrhea=dict(
                title="No. of Under-5s with uncomplicated Fever",
                get_value=lambda: self.get_base_indicator("under5_diarrhea")
            )
        )

    @memoized
    def get_base_indicator(self, prefix):
        totals = 0
        for user_id in self.user_ids:
            couch_key = ["user", self.domain, user_id, prefix]
            data = get_db().view('mvp/under5_child_health',
                reduce=True,
                startkey=couch_key+[self.datespan.startdate_param_utc],
                endkey=couch_key+[self.datespan.enddate_param_utc]
            ).first()
            if data:
                totals += data.get('value', 0)
        return totals