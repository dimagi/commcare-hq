import calendar
import datetime
import math
import dateutil
from django.utils.safestring import mark_safe
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport
from dimagi.utils.couch.database import get_db

class MVISHealthCoordinatorReport(CustomProjectReport):
    """
        This report needs some serious cleanup. Did Child Health data one way when a
        different way would have made it more general to calculate all of the data.
        At some point this should get moved over and not look so gross. Sorry.
    """
    fields = []
    slug = "health_coordinator"
    name = "MVIS Health Coordinator Report"
    report_template_path = "mvp/reports/health_coordinator.html"
    flush_layout = True
    hide_filters = True

    @property
    def report_context(self):
        context = super(MVISHealthCoordinatorReport, self).report_context

        date_format = "%b %Y"

        date_ranges = list()
        now = datetime.datetime.utcnow()
        last_start = datetime.datetime(now.year, now.month, 1, hour=0, minute=0, second=0, microsecond=0)
        current_range = self._date_range(last_start, 0)
        date_ranges.append(dict(label=mark_safe("%s<br />(Current)" % now.strftime(date_format)), range=current_range))
        last_start = current_range.get('start')

        for i in range(1,13):
            date_range = self._date_range(last_start)
            last_start = date_range.get('start')
            date_ranges.append(dict(label=mark_safe("%s<br />(-%d)" % (last_start.strftime(date_format), i)), range=date_range))

        dr_first = date_ranges[0].get('range',{})
        self.get_household_cases_for_range(dr_first.get('start'), dr_first.get('end'))

        self.child_indicators = [
            dict(
                title="Proportion of Under-5's with uncomplicated fever who recieved RDT test",
                n_key='N_28',
                d_key='D_28'
            ),
            dict(
                title="Proportion of Under-5's with uncomplicated fever who recieved RDT test and were RDT positive",
                n_key='N_29',
                d_key='N_28'
            ),
            dict(
                title="Proportion of Under-5's with positive RDT result who received antimalarial/ADT medication",
                n_key='N_20',
                d_key='N_29'
            ),
            dict(
                title="Proportion of Under-5's with uncomplicated fever who did NOT receive RDT "
                "test due to 'RDT not available' with CHW",
                n_key='N_48',
                d_key='D_28'
            )
        ]
        for indicator in self.child_indicators:
            indicator.update(values=list())

        self.general_indicators = [
            dict(
                title="Proportion of Households receiving on-time routine visit within last 90 DAYS",
                get_n=lambda start, end: self.get_household_visits_for_range(start, end, three_month=True),
                get_d=lambda start, end: self.get_household_cases_for_range(start, end, three_month=True)
            ),
            dict(
                title="Proportion of Households receiving on-time routine visit within last 30 DAYS",
                get_n=lambda start, end: self.get_household_visits_for_range(start, end),
                get_d=lambda start, end: self.get_household_cases_for_range(start, end)
            ),
            dict(
                title="Proportion of Households with an UNDER-5 CHILD receiving on-time routine visit"
                    " within last 30 DAYS",
                get_n=lambda start, end: self.get_household_visits_for_range(start, end, special="under5"),
                get_d=lambda start, end: self.get_household_cases_for_range(start, end, special="under5")
            ),
            dict(
                title="Proportion of Households with a PREGNANT WOMAN receiving on-time routine visit "
                        "within last 30 DAYS",
                get_n=lambda start, end: self.get_household_visits_for_range(start, end, special="pregnant"),
                get_d=lambda start, end: self.get_household_cases_for_range(start, end, special="pregnant")
            ),
            dict(
                title="Proportion of Households with a NEONATE (NEWBORN LESS THAN 30 DAYS OLD) receiving "
                        "on-time routine visit within last 7 DAYS",
                get_n=lambda start, end: self.get_household_visits_for_range(start, end, special="neonate"),
                get_d=lambda start, end: self.get_household_cases_for_range(start, end, special="neonate")
            )
        ]
        for indicator in self.general_indicators:
            indicator.update(values=list())

        for dr in date_ranges:
            date_range = dr.get('range', {})
            self.compute_child_indicators_for_range(
                dr.get('label'),
                date_range.get('start'),
                date_range.get('end')
            )
            self.compute_indicators_for_range(
                dr.get('label'),
                date_range.get('start'),
                date_range.get('end')
            )

        def _format_summary_indicator(num, den, percent):
            return dict(
                n=num,
                d=den,
                percent=percent,
                text="%.f%%" % percent
            )

        all_indicators = self.child_indicators + self.general_indicators
        for indicator in all_indicators:
            indicator['values'].reverse()
            n_vals = [v.get('value',{}).get('n', 0) for v in indicator['values']
                         if v.get('value', {}).get('d', 0)]
            n_vals.sort()
            n_avg = self._calc_avg(n_vals)
            n_median = self._calc_median(n_vals)
            n_std_dev = self._calc_std_dev(n_vals)

            d_vals = [v.get('value',{}).get('d', 0) for v in indicator['values']
                         if v.get('value', {}).get('d', 0)]
            d_vals.sort()
            d_avg = self._calc_avg(d_vals)
            d_median = self._calc_median(d_vals)
            d_std_dev = self._calc_std_dev(d_vals)

            percent_vals = [v.get('value', {}).get('percent', 0) for v in indicator['values']
                            if v.get('value', {}).get('d', 0)]
            percent_vals.sort()
            percent_avg = self._calc_avg(percent_vals)
            percent_median = self._calc_median(percent_vals)
            percent_std_dev = self._calc_std_dev(percent_vals)

            indicator.update(
                average=_format_summary_indicator(n_avg, d_avg, percent_avg),
                median=_format_summary_indicator(n_median, d_median, percent_median),
                std_dev=_format_summary_indicator(n_std_dev, d_std_dev, percent_std_dev)
            )

        context.update(
            headers=[ind.get('label') for ind in all_indicators[0].get('values', [])],
            indicators=all_indicators,
        )

        return context

    def compute_indicators_for_range(self, range_label, startdate, enddate):
        for indicator in self.general_indicators:
            get_n = indicator.get('get_n')
            get_d = indicator.get('get_d')
            indicator['values'].append(dict(
                label=range_label,
                value=self._format_indicator(get_n(startdate, enddate), get_d(startdate, enddate))
            ))

    def get_household_visits_for_range(self, startdate, enddate,
                                       three_month=False, special=None):
        """
            Number of unique households who have received a CHW visit in the past N Days
        """
        key_by = special if special else "visit"

        couch_key = [self.domain, key_by]
        if three_month:
            startdate = startdate-datetime.timedelta(days=90)
            startdate = startdate.replace(day=1)
        data = get_db().view('mvp/household_visits',
            reduce=False,
            startkey=couch_key+[startdate.isoformat()],
            endkey=couch_key+[enddate.isoformat(), {}]
        ).all()
        household_case_ids = set([item.get('key', [])[-1] for item in data])
        return len(household_case_ids)

    def get_household_cases_for_range(self, startdate, enddate, three_month=False, special=None):
        key_by_special = dict(
            default="",
            under5=" dob",
            neonate=" dob",
            pregnant=" pregnancy"
        )
        special_key = key_by_special.get(special or "default", "")

        if three_month:
            # sorry, lots of lazy going on
            startdate = startdate-datetime.timedelta(days=90)
            startdate = startdate.replace(day=1)

        compute_by_special = dict(
            default=lambda x: x,
            under5=lambda x: self._is_dob_special(x, startdate, enddate),
            neonate=lambda x: self._is_dob_special(x, startdate, enddate, special="neonate_until"),
            pregnant=lambda x: self._is_pregnancy_valid(x, startdate, enddate)
        )
        compute_value = compute_by_special.get(special or "default")

        # Closed Cases Opened Before the End Date (cco)
        key = [self.domain, "opened_on closed%s" % special_key]
        cco, cco_values = self.get_household_cases_and_values(
            key,
            key+[enddate.isoformat(), {}],
            compute_value
        )

        # Closed Cases Closed Before the Start Date (ccc)
        key[1] = "closed_on closed%s" % special_key
        ccc, ccc_values = self.get_household_cases_and_values(key,
            key+[startdate.isoformat(), {}],
            compute_value
        )
        valid_closed_cases = cco.difference(ccc)

        # Currently Open Cases Opened Before the End Cate (oco)
        key[1] = "opened_on open%s" % special_key
        oco, oco_values = self.get_household_cases_and_values(
            key,
            key+[enddate.isoformat(), {}],
            compute_value
        )

        valid_cases = oco.union(valid_closed_cases)
        all_values = dict(cco_values+ccc_values+oco_values)
        return sum([all_values.get(c, 0) for c in valid_cases])

    def get_household_cases_and_values(self, startkey, endkey, compute_value):
        data = get_db().view("mvp/household_cases_opened_on",
            reduce=False,
            startkey=startkey,
            endkey=endkey
        ).all()
        values = [(item.get('key', [])[-1], compute_value(item.get('value', 1))) for item in data]
        cases = set([item.get('key', [])[-1] for item in data])
        return cases, values

    def _get_valid_datetime(self, dt):
        if isinstance(dt, str) or isinstance(dt, unicode):
            return dateutil.parser.parse(dt, ignoretz=True)
        return dt

    def _is_dob_special(self, dob_data, startdate, enddate, special="under5_until"):
        is_valid, dob = self._is_baby_valid(dob_data, startdate, enddate)
        special_until = dob_data.get(special)
        if is_valid and special_until:
            special_until = self._get_valid_datetime(special_until)
            if special_until > startdate:
                return 1
        return 0

    def _is_baby_valid(self, dob_data, startdate, enddate):
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

    def _is_pregnancy_valid(self, pregnancy_data, startdate, enddate):
        preg_start = pregnancy_data.get('case_opened')
        preg_end = pregnancy_data.get('case_closed')
        if preg_start and preg_end:
            preg_start = self._get_valid_datetime(preg_start)
            preg_end = self._get_valid_datetime(preg_end)
            if (preg_end > startdate) and (preg_start >= startdate) and (preg_start < enddate):
                return 1
        return 0

    def compute_child_indicators_for_range(self, range_label, startdate, enddate):
        # todo kind of messy. clean up
        self._startdate = startdate
        self._enddate = enddate
        for indicator in self.child_indicators:
            indicator['values'].append(dict(
                label=range_label,
                value=self._format_indicator(self.get_part_from_child(indicator.get('n_key')),
                    self.get_part_from_child(indicator.get('d_key')))
            ))
        self._child_indicator_parts = None

    _child_indicator_parts = None
    @property
    def child_indicator_parts(self):
        if self._child_indicator_parts is None:
            parts = dict(
                D_28=dict(key="under5_fever",
                    couch_view='mvp/under5_child_health'),
                N_28=dict(key="under5_fever rdt_test_received",
                    couch_view='mvp/under5_child_health'),
                N_29=dict(key="under5_fever rdt_test_received rdt_test_positive",
                    couch_view='mvp/under5_child_health'),
                N_20=dict(key="under5_fever rdt_test_received rdt_test_positive anti_malarial",
                    couch_view='mvp/under5_child_health'),
                N_48=dict(key="under5_fever rdt_not_available",
                    couch_view='mvp/under5_child_health')
            )
            for key, val in parts.items():
                couch_key = [self.domain, val.get('key', "")]
                data = get_db().view(val.get('couch_view', ""),
                    reduce=True,
                    startkey=couch_key+[self._startdate.isoformat()],
                    endkey=couch_key+[self._enddate.isoformat()]
                ).first()
                val['value'] = data.get('value', 0) if data else 0
            self._child_indicator_parts = parts
        return self._child_indicator_parts

    def get_part_from_child(self, key):
        return self.child_indicator_parts.get(key, {}).get('value', 0)

    def _calc_avg(self, vals):
        if len(vals) > 0:
            return int(round(sum(vals)/float(len(vals))))
        return 0

    def _calc_median(self, vals):
        if len(vals) > 0:
            if len(vals) % 2 == 1:
                return vals[(len(vals)-1)/2]
            lower = vals[max((len(vals)/2)-1,0)]
            upper = vals[-len(vals)/2]
            return int(round((lower+upper)/2.0))
        return 0

    def _calc_std_dev(self, vals):
        if len(vals) > 0:
            mean = sum(vals)/float(len(vals))
            var = [(v-mean)*(v-mean) for v in vals]
            var_avg = sum(var)/float(len(var))
            return int(round(math.sqrt(var_avg)))
        return 0

    def _date_range(self, last_start, offset=7):
        current=last_start-datetime.timedelta(days=offset)
        ranges = calendar.monthrange(current.year,current.month)
        return dict(
            start=datetime.datetime(current.year, current.month, 1, hour=0, minute=0, second=0, microsecond=0),
            end=datetime.datetime(current.year, current.month, ranges[1], hour=23, minute=59, second=59, microsecond=999999)
        )

    def _format_indicator(self, numerator, denominator):
        try:
            percent = float(numerator)/float(denominator)*100
        except ZeroDivisionError:
            percent = 0
        return dict(n=numerator, d=denominator, percent=percent, text="%.f%%" % percent )
