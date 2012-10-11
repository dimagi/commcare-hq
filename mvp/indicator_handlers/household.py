import datetime
import dateutil
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from mvp.indicator_handlers import IndicatorHandler

class HouseholdIndicatorHandler(IndicatorHandler):

    @property
    @memoized
    def datespan_90(self):
        startdate_90 = self.datespan.startdate - datetime.timedelta(days=90)
        if self.datespan.startdate.day == 1:
            # It's likely that 90 days ago means past 3 months
            startdate_90.replace(day=1)
        return DateSpan(
            startdate_90,
            self.datespan.enddate,
            self.datespan.format,
            self.datespan.inclusive,
            self.datespan.timezone,
        )

    @property
    @memoized
    def indicators(self):
        return dict(
            num_households=dict(
                title="Number of Households",
                get_value=lambda: self.get_household_cases("all")
            ),
            household_ontime_visit_90=dict(
                title="Proportion of Households receiving on-time routine visit within last 90 DAYS",
                get_value=lambda: dict(
                        numerator=self.get_household_visits("visit", True),
                        denominator=self.get_household_cases("all", True)
                    )
            ),
            household_ontime_visit=dict(
                title="Proportion of Households receiving on-time routine visit within last 30 DAYS",
                get_value=lambda: dict(
                        numerator=self.get_household_visits("visit"),
                        denominator=self.get_household_cases("all")
                    )
            ),
            household_ontime_under5_visit=dict(
                title="Proportion of Households with an UNDER-5 CHILD receiving on-time routine visit"
                      " within last 30 DAYS",
                get_value=lambda: dict(
                        numerator=self.get_household_visits("under5"),
                        denominator=self.get_household_cases("under5")
                    )
            ),
            household_ontime_neonate_visit=dict(
                title="Proportion of Households with a NEONATE (NEWBORN LESS THAN 30 DAYS OLD) receiving "
                      "on-time routine visit within last 7 DAYS",
                get_value=lambda: dict(
                        numerator=self.get_household_visits("neonate"),
                        denominator=self.get_household_cases("neonate")
                    )
            ),
            household_ontime_pregnant_visit=dict(
                title="Proportion of Households with a PREGNANT WOMAN receiving on-time routine visit "
                      "within last 30 DAYS",
                get_value=lambda: dict(
                        numerator=self.get_household_visits("pregnant"),
                        denominator=self.get_household_cases("pregnant")
                    )
            )
        )

    @memoized
    def get_household_visits(self, type, ninety_days=False):
        datespan = self.datespan_90 if ninety_days else self.datespan
        couch_key = [self.domain, type]
        data = get_db().view('mvp/household_visits',
            reduce=False,
            startkey=couch_key+[datespan.startdate_param_utc],
            endkey=couch_key+[datespan.enddate_param_utc, {}]
        ).all()
        household_case_ids = set([item.get('key', [])[-1] for item in data])
        return len(household_case_ids)


    @memoized
    def get_household_cases(self, type, ninety_days=False):
        datespan = self.datespan_90 if ninety_days else self.datespan

        special_key_by_type = dict(
            all="",
            under5=" dob",
            neonate=" dob",
            pregnant=" pregnancy"
        )
        special_key = special_key_by_type.get(type)

        filter_by_type = dict(
            all=lambda data: data,
            under5=lambda data: self._validate_dob(data, "under5_until", datespan.startdate, datespan.enddate),
            neonate=lambda data: self._validate_dob(data, "neonate_until", datespan.startdate, datespan.enddate),
            pregnant=lambda data: self._validate_pregnancy(data, datespan.startdate, datespan.enddate)
        )
        filter_fn = filter_by_type.get(type)

        # Closed Cases Opened Before the End Date (cco)
        key = [self.domain, "opened_on closed%s" % special_key]
        cco, cco_values = self._get_household_cases_and_values(
            key,
            key+[datespan.enddate_param_utc, {}],
            filter_fn
        )

        # Closed Cases Closed Before the Start Date (ccc)
        key[1] = "closed_on closed%s" % special_key
        ccc, ccc_values = self._get_household_cases_and_values(key,
            key+[datespan.startdate_param_utc, {}],
            filter_fn
        )
        valid_closed_cases = cco.difference(ccc)

        # Currently Open Cases Opened Before the End Cate (oco)
        key[1] = "opened_on open%s" % special_key
        oco, oco_values = self._get_household_cases_and_values(
            key,
            key+[datespan.enddate_param_utc, {}],
            filter_fn
        )

        valid_cases = oco.union(valid_closed_cases)
        all_values = dict(cco_values+ccc_values+oco_values)
        return sum([all_values.get(c, 0) for c in valid_cases])

    def _get_household_cases_and_values(self, startkey, endkey, filter_fn):
        data = get_db().view("mvp/household_cases",
            reduce=False,
            startkey=startkey,
            endkey=endkey
        ).all()
        values = [(item.get('key', [])[-1], filter_fn(item.get('value', 1))) for item in data]
        cases = set([item.get('key', [])[-1] for item in data])
        return cases, values

    def _get_valid_datetime(self, dt):
        if isinstance(dt, str) or isinstance(dt, unicode):
            return dateutil.parser.parse(dt, ignoretz=True)
        return dt

    def _validate_pregnancy(self, data, startdate, enddate):
        preg_start = data.get('case_opened')
        preg_end = data.get('case_closed')
        if preg_start and preg_end:
            preg_start = self._get_valid_datetime(preg_start)
            preg_end = self._get_valid_datetime(preg_end)
            if (preg_end > startdate) and (preg_start >= startdate) and (preg_start < enddate):
                return 1
        return 0

    def _validate_dob(self, data, data_key, startdate, enddate):
        is_valid, dob = self._is_baby_alive(data, startdate, enddate)
        special_until = data.get(data_key)
        if is_valid and special_until:
            special_until = self._get_valid_datetime(special_until)
            if special_until > startdate:
                return 1
        return 0

    def _is_baby_alive(self, dob_data, startdate, enddate):
        dob = dob_data.get('value')
        if dob:
            dob = self._get_valid_datetime(dob)
            if dob < enddate:
                is_dead = dob_data.get('is_dead', False)
                death_date = dob_data.get('closed_on')
                if is_dead and death_date:
                    death_date = self._get_valid_datetime(death_date)
                    if death_date > startdate:
                        return True, dob
                else:
                    return True, dob
        return False, dob